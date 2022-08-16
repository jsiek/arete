# Arete

Arete is an experimental programming language.

It currently includes

* parallelism (via futures)

* controlled mutability for data-race freedom, memory safety, etc.
  via dynamic tracking of fractional permissions.
  
* semi-automatic memory management via fractional permissions
  
* gradual typing (but not yet sound gradual typing)

* modules

and there are plans to add:

* static tracking of fractional permissions

* generics with contraints

* more features for asynchronous and parallel programming.

The design of Arete is currently captured in a prototype
implementation written in Python 3.10 that includes:

* grammar and parser ([Arete.lark](Arete.lark) and [parser.py](parser.py))
  using the [Lark](https://github.com/lark-parser/lark) parser generater.

* constant evaluation ([const_eval.py](const_eval.py))

* type checking ([type_check.py](type_check.py))

* desugaring ([desugar.py](desugar.py))

* interpreting (an abstract machine) ([machine.py](machine.py))

The design of Arete is based on discussions with Dave Abrahams and
Dimitri Racordon about their Val language and it is influenced by the
design of the Carbon language.


# Examples

There are lots of small example programs in the [tests](tests)
directory, including [double-linked lists](tests/dlist.rte), [binary
trees](tests/avl.rte), and [parallel merge
sort](tests/par_merge_sort.rte).

Here we look at a couple examples that demonstrate how mutation is
controlled via fractional permissions in Arete.

Mutable variables are declared with `var` and immutable ones are
declared with `let`. For example, the following program runs without
error and returns `0`.

	fun main() {
	  var x = 42;
	  let y = 40;
	  x = x - y;
	  return x - 2;
	}

Both `var` and `let` variables are by-reference (in C++ lingo); they
are aliases for the value produced by their initializing expression
(like all variables in Java).  In the following, we initialize `y`
with `x` and declare `y` to also be a mutable variable. We then write
`0` to `y` and try to return `x + y`.

	fun main() {
	  var x = 42;
	  var y = x;
	  y = 0;
	  return x + y;
	}

This program halts with an error when we try to read `x` in `x + y`, 
saying that the pointer (associated with `x`) does not have
read permission.

In Arete, each pointer has a fraction to control whether it is allowed
to read or write. A pointer with positive fraction may read and a
pointer with a fraction of `1` may write.

The pointer associated with variable `x` starts out with a permission
of `1`, but when we initialize `y` with `x`, all of its permission is
transfered to the new pointer for `y`. So the write to `y` executes
successfully, but the later read of `x` is an error because by that
time, `x` has `0` permission.

Getting back to the first example, we discuss memory allocation
and deallocation.

	fun main() {
	  var x = 42;
	  let y = 40;
	  x = x - y;
	  return x - 2;
	}

When `x` is initialized with `42`, memory for `42` is allocated and
the resulting pointer is associated with `x` (with permission
`1`). Likewise for when `y` is initialized with `40`.  The variables
`x` and `y` go out of scope at the end of the function, after the
`return`. When they go out of scope, the associated pointers are
*killed*, and because those pointers have permission `1`, the memory
at their address is deallocated.

In this way, memory deallocation is often handled automatically in Arete.
However, when dealing with data structures that contain cycles, some
manual effort is needed. The following example creates a tuple
that contains a pointer to itself.

	fun main() {
	  var x = ⟨0, 1⟩;
	  x[1] = &x;
	  return x[0];
	}

The `x` goes to 0 permission on the assignment `x[1] = &x`, so when
`x` goes out of scope, the tuple does not get deallocated.
So this program halts with an error.


# Specification 

This is the current specification of the Arete language.

**Table of Contents**

* [Values](#values)

* [Types](#types)

* [Machine](#machine)

* [Language Features](#features)

    * [Auxiliary Syntax](#auxiliary)

    * [Definitions](#definitions)
	
	* [Statements](#statements)
	
	* [Expressions](#expressions)

# <a name="values"></a>Results and Values 

The *result* of an expression consists of a value (described next) and
a Boolean flag that says whether the value was newly created by the
expression (it's a temporary) or not.

A *value* is the runtime object produced by an expression during
program execution. The kinds of values in Arete are listed below.

The Python classes that representation values are defined in
[values.py](values.py).

All values are first class in the sense that they can be stored in
memory, passed as argument to functions, etc.

We define the term *environment* to be a dictionary mapping variable
names to pointers. (Pointers are a kind of value defined below.)

## Numbers

The numbers currently include integers and fractions.

## Booleans

The values `true` and `false`.

## Tuples

A tuple is a sequence of values.
For example, 

```
⟨0,true,2,⟨10,false,12,13⟩,4,5⟩
```

## Pointers

A pointer includes the following fields:

* `address` (an integer)
* `path` (list of integers)
* `permission` (fraction)
* `lender` (another pointer, optional)
* `kill_when_zero` (a Boolean)

If the value at `address` in memory is a tuple, then the `path`
specifies which part of the tuple this pointer is referring to.
The path is a list and not just a single integer because tuples
can be nested. So, for example, the path `[3,2]` refers to
the location of `12` in the tuple `⟨0,1,2,⟨10,11,12,13⟩,4,5⟩`.

A pointer whose `permission` is `0` or greater can be copied.
A pointer whose `permission` is greater than `0` can be used for
reading.
A pointer whose `permission` is `1` can be used for writing.

If the pointer is a copy of another pointer, then its `lender` is that
other pointer.

If the `kill_when_zero` flag is set to true, then the pointer is
killed when its `permission` reaches zero. This flag is needed for
`let` variables.

A *null* pointer is a pointer whose `address` is `None`.

We define the following operations on pointers.

### Kill

We define a *live pointer* to be a pointer whose `address` field
contains an integer (and not `None`). If a pointer is not live,
it's *dead*.

We define the *living lender* of a pointer `P` to be the first live
pointer in the chain of pointers obtain by following the `lender`
fields starting with pointer `P`.

1. If the pointer has a living lender, then transfer all of this
   pointer's permission to the living lender.
   
2. If the pointer does not have a living lender

    a. if its permission is `1`, delete the memory at its `address`.
	
	b. if its permission is greater than `0` but less than `1`, 
	   halt with an error.

3. Set the `address` of this pointer to `None`.


### Duplicate

Inputs: percentage

1. If the pointer is null, return a null pointer.

2. If the pointer is alive, create a new pointer with the same address
   and path and transfer the given percentage from this pointer to the new
   pointer.  Return the new pointer.

### Transfer

Inputs: source pointer, percentage

Let `amount` be the permission of the source pointer multiplied by the
given percentage.  Decrease the permission of the source pointer by
`amount` and increase the permission of this pointer by `amount`.
If the permission of the source pointer becomes `0` and its
`kill_when_zero` flag is true, then kill it.

### Upgrade

If the pointer has a living lender, transfer all of the lender's
permission to this pointer. Return `true` or `false` corresponding to
whether this pointer's permission is equal to `1`.

## Pointer Offset

We sometimes need to delay the duplication of a pointer when using it
to index into a tuple, which we accomplish with another pointer-like
value called a *pointer offset*, which has the following fields.

* `ptr` (a Pointer)
* `offset` (an integer)

A pointer offset acts like its underlying `ptr` but with the given
`offset` appended to the end of its `path`.


## Closures

A closure includes information from the originating function (name,
parameters, body, etc.) and an environment.

## Futures

A *future* value has an associated thread. 

## Modules

A module has a name, an environment of exported members, and an
environment of all its members.

# <a name="types"></a>Types

A comma-separated list of types is a `type_list`.

```
<type_list> ::= <type> | <type> , <type_list>
```

## Array Type

```
<type> ::= [ <type> ]
```

## Boolean Type

```
<type> ::= bool
```

## Function Type

```
<type> ::= ( <type_list> ) -> <type>
```

## Integer Type

```
<type> ::= int
```

## Rational Type

```
<type> ::= rational
```

## Recursive Type

```
<type> ::= rec <identifier> in <type>
```

The `identifier` may occur inside the `type` expression and represents
the whole `type`. For example, the following type could be used to
represent a singly-linked list of integers. Each node is a tuple whose
first element is an integer and whose second element is a pointer to
another node.

```
rec X ⟨ int, X* ⟩
```

(Recursive types are unweildy to deal with directly, so there are
plans to add syntactic sugar for them.)

## Tuple Type

```
<type> ::= ⟨ <type_list> ⟩
```

## Unknown Type (aka. the "any" type or the "dynamic" type)

```
<type> ::= ?
```

This type enables gradual typing.


## Type Variables

```
<type> ::= <identifier>
```

An occurence of a type variable refers to a recursive type.
(See the above entry about Recursive Types.)


# <a name="machine"></a>Machine Description

The *machine* has

* `memory` that maps an address (integer) to a value,

* collection of `threads` including the `current_thread`
  and the `main_thread`.

* `result` which eventually holds the value returned by the `main`
  function.

Each *thread* has

* `stack` of *frames* (the procedure call stack), 
  with one *frame* for each function call.
* `result` which eventually holds the value produced by the thread.
* `parent` the thread that spawned this thread (optional).
* `num_children` the number of threads spawned by this thread that
    are still running.

Each *frame* has a stack named `todo` of *node runners*.

A *node runner* is responsible for executing one node in the abstract
syntax tree of the program. Think of each node runner as a little
state machine. (It's named "node runner" because I use to enjoyed playing
[Lode Runner](https://loderunnerwebgame.com/game/) in the 1980's.)
Each node runner has

* `ast` (the AST node)

* `state` an integer to indicate how far along the node runner is in
   executing this AST node.
   
* `results` a list of value-context pairs, where the values are the
   results of the subexpressions of this AST node. The contexts
   are the contexts for the subexpressions.
   (More about contexts below.)
   
* `context` specifies whether the expression should be evaluated for
   its value (aka. rvalue) via `ValueCtx` or its address (aka. lvalue)
   via `AddressCtx`. The context also specifies what `percentage` of
   its permission is being requested and whether to `duplicate` the
   result (the default is yes, duplicate the pointer).

* `return_value` is to propagate the result of a `return` statement.

* `return_mode` (the strings `value` or `address`) is whether the enclosing
  function expects to return a value or address.

* `env` an environment mapping all the in-scope variables to their addresses.

## Machine Operations

We define the following verbs, i.e., operations that the machine can
perform. (These correspond to methods in the `Machine` class.)

### Current Frame

The *current frame* is the frame at the top of the `stack` of the
current thread.

### Current Runner

The *current runner* is the node runner at the top of the `todo`
stack of the current frame.

### Current Environment

The *current environment* is the environment (`env`) of the current
node runner.

### Schedule an AST node

Inputs: AST node, environment, context (defaults to value at 50%),
return mode (optional).

1. Create a node runner with the given inputs. If the return mode is
   not given, use the return mode of the current runner.

2. Push the node runner onto the `todo` stack of the current
   frame. 
   
3. Return the node runner.

### Finish Expression

Inputs: result value

Let `C` be the context of the current node runner.

1. Kill all the entries in `results` whose subexpressions were
   evaluated in a `duplicate` context. (This is why we store the
   contexts in the `results` list).
   
2. Pop the current runner from the `todo` stack of the current frame.

3. If the `todo` stack of the current frame is not empty, 
   push the result value paired with context `C` onto the `results`
   of the current node runner.

4. Otherwise, if the `stack` of the current thread is not empty,
   pop the current frame from the `stack` and then set the
   `return_value` of the current runner to the result value.
   
5. Otherwise, set the `result` of the current thread to the result
   value.

### Finish Statement

UNDER CONSTRUCTION

### Finish Definition

UNDER CONSTRUCTION

### Spawn

UNDER CONSTRUCTION

## Memory Operations

### Read

Inputs: pointer, context

UNDER CONSTRUCTION

### Write

UNDER CONSTRUCTION

### Deallocate

Inputs: address

1. Kill the value that is in memory at the given address.

2. Delete the entry for this address in the memory.



# <a name="features"></a>Language Features

This section is organized according to the grammar of the language,
which has three main categories: expressions, statements, and
definitions. Within each category, the entries are ordered
alphabetically. Each entry describe both the syntax of the language
feature and its runtime behavior (semantics).  The syntax given here
is a somewhat simplified variant that does not include the encoding of
precedence.  For the exact grammar rules, see
[Arete.lark](Arete.lark). Likewise, for the fully precise
specification of its runtime behavior, read the `step` method of the
corresponding Python class in
[abstract_syntax.py](abstract_syntax.py).

A *program* is a list of zero or more definitions:

```
<definition_list> ::=   | <definition> <definition_list>
```

Program execution begins with a call to the function named `main` with
no arguments. Once the execution of `main` is finished, the program
exits with the return value of `main` provided memory is empty. If
memory is non-empty, then the program halts with an error. If there
is no such `main` function, the program halts with an error.

## <a name="auxiliary"></a>Auxiliary Syntax

This section is about auxilliary syntactic categories that are used
later in the definitions of the expressions, statements, and
definitions.

```
<parameter> ::= [<privilege>] <identifier> [: <type>]
```

The `parameter` category is used for function parameters and other
variable definitions (e.g. the `let` statement). (See the 
definition of `privilege` below.) If no type annotation is present,
the parameter is given the unknown type `?`.

```
<privilege> ::=   | ! | @
```

The `privilege` specifies the permissions required of any argument
value bound to the associated parameter. The notation `!` is for
writable (fraction `1`), `@` is for no requirement (any fraction), and
the default is readable (any fraction greater than `0`).

```
<initializer> ::= <expression> | <expression> of <expression>
```

An initializer specifies what percentage of the permission is taken
from the result value of the given expression. For example, the
following initializes variable `y` to be an alias of variable `x`,
taking 50% of its permissions.

```
let y = 1/2 of x;
```

If no percentage is specified and the context of the current node
runner is an `AddressCtx`, then use that context's
percentage. Otherwise use 50%.

## <a name="definitions"></a>Definitions

### Constant

```
<definition> ::= const <identifier> [: <type>] = <expression>;
```

### Import

```
<definition> ::= from <expression> import <identifier_list>;
```

### Function

```
<definition> ::= fun <identifier> (<parameter_list>) [-> <type>] [<return_mode>] <block>
```

### Module

```
<definition> ::= module <identifier> exports <identifier_list> { <definition_list> }
```

### Type Alias

```
<definition> ::= type <identifier> = <type>;
```

### Variable (Global)

```
<definition> ::= let <identifier> [: <type>] = <expression>;
```

## <a name="statements"></a>Statements 

### Assert

```
<statement> ::= assert <expression>;
```

Evaluate the `expression` and halt the program if the result is `false`.

### Assignment (Write)

```
<statement> ::= <expression> = <initializer>;
```

1. Schedule the `initializer` in a value context with duplication
  requesting 50%.
  
2. Schedule the `expression` in an address context with duplication
  requesting 100%. The result must be a pointer.

3. Write the result of the initializer to the pointer.

4. Finish this statement.

(The order of evaluation here does not follow our usual left-to-right
 policy. Using left-to-right for assignment triggers errors in many of
 our test cases. I have not yet investigated why this is.)


### Block

```
<statement> ::= { <statement_list> }
```

### Delete

```
<statement> ::= delete <expression>;
```

1. Schedule the `expression` in value context with duplication
   requesting 100%. The result must be a pointer.

2. Deallocate the memory associated with the pointer.


### Expression Statement

```
<statement> ::= ! <expression>;
```

Evaluate the `expression` for its effects and discard the result.

(Note: the `!` is there to make the grammar unambiguous, which sucks.
This needs work.)

### If

```
<statement> ::= if (<expression>) <block>
<statement> ::= if (<expression>) <block> else <block>
```

### Local Variable (Let)

```
<statement> ::= let <parameter> = <initializer>; <statement_list>
```

1. Schedule the `initializer` in the current environment, with context
   `AddressCtx` with duplication, requesting the appropriate
   percentage of permission corresponding to the privilege level of
   the `parameter` (1 for writable, 1/2 for readable, 0 for none).

2. Copy the current environment and name it `body_env`.
   
3. Check that the initializer's result is a pointer and has the
   permission required by the privilege level of the `parameter`.
   
4. Update `body_env` to map the identifier of the `parameter` to the
   initializer's result.

5. Schedule the following statements in the environment `body_env`.

6. Once the following statements are complete, 
   kill the initializer's result. 
   
```
<statement> ::= var <identifier> = <expression>;
```

The `var` statement desugars into a `let` statement as follows.

```
var x = e;
```
turns into
```
let !x = 1/1 of e;
```

That is, the permission level of `x` is writable and the
requested percentage is 100%.


### Return

```
<statement> ::= return <expression>;
```

1. Schedule the `expression`. If the `return_mode` of the current node
   runner is `value`, using `ValueCtx` with duplication and 100%. If
   the `return_mode` is `address`, use `AddressCtx` with duplication
   and 100%.

2. Set the `return_value` of the current node runner to
   a duplicate (at 100%) of the expression's result.

3. Finish this statement.


### Transfer Permission

```
<statement> ::= <expression> <- <expression> of <expression>
```


### While

```
<statement> ::= while (<expression>) <block>
```

Repeatedly execute the `block` so long as the `expression` evaluates to `true`.


## <a name="expressions"></a>Expressions


**Table of Contents**

* [Address Of](#addressof)
* [Array Creation](#array)
* [Call](#call) a fuction
* [False Literal](#false)
* [Function (Lambda)](#function)
* [Index](#index) (into a tuple or array)
* [Integer Literal](#integer)
* [Member Access](#member)
* [Null Pointer Literal](#null)
* [Primitive Call](#primitive)
* [True Literal](#true)
* [Tuple Creation](#tuple)
* [Variable](#variable)
* [Spawn](#spawn) a future
* [Wait](#wait) on a future

### <a name="addressof"></a>Address Of

```
<expression> ::= & <expression>
```

1. Schedule `expression` in address context, requesting 100% of its
   permission, and with duplication as specified by the current
   node runner's context.
   
2. If the current node runner's context is a value context,
   if the context is with duplication, let `result` be
   a duplicate of the result of `expression`, taking
   the percentage specified by the runner's context.
   If the context is without duplication, let `result` be
   the result of `expression`.

3. If the current node runner's context is an address context, 
   halt with an error.

4. Finish this expression with `result`.


### <a name="array"></a>Array Creation

```
<expression> ::= [ <expression> of <expression> ]
```

UNDER CONSTRUCTION


### <a name="call"></a>Call

```
<expression> ( <initializer_list> )
```

1. Schedule the `expression` in value context with duplicaton
   requesting `1/2` permission.  The result must be a closure.

2. Schedule each `initializer` (left to right) in address context
   requesting the percentage appropriate to the corresponding
   parameter of the closure. (Same as for `let` statements.)
   
3. Copy the closure's environment into `body_env`. Add an item to
   `body_env`, mapping each parameter to the corresponding result from
   its initializer.  Check that the initialer is a pointer and has
   enough permission for the privilege level of the parameter and
   halt with an error if the permission is too low.

4. Create a new frame and push it onto the `stack` of the current thread.
   
5. Schedule the body of the closure with the environment `body_env`
   and the closure's return mode.

6. Upon completion of the body, kill all of the initializers.
   If the current node runner's `return_value` is `None`,
   set it to the void value.
   
     a. If the current node runner's context is a value context, and
        its return mode is `value`, let `result` be the runner's
        `return_value`.  If the runner's return mode is `address`,
        then the runner's `return_value` is a pointer; let `result` be
        the value read from memory at that address.  Kill the pointer.

     b. If the current node runner's context is a address context, and
	    its return mode is `value`, allocate the runner's `return_value`
		in memory and let `result` be the new address.
		If the return mode is `address`, let `result` be the 
        runner's `return_value`.

7. Finish this expression with `result`.


### <a name="false"></a>False Literal

```
<expression> ::= false
```

(Similar to the case for integer literals.)

### <a name="function"></a>Function (aka. lambda, anonymous function)

```
<expression> ::= fun ( <parameter_list> ) <return_mode> <block>
```

The *free variables* of a function are those variables that occur
inside `block` without an enclosing variable binding in the `block` or
by this function's parameters.

1. Create an environment named `clos_env` with a duplicate (50%)
   for each free variable of the function.
2. Create a closure value with the `clos_env` and the other
   information from this function (parameter list, return mode, and body).
3. If the current node runner's context is a value context,
   let `results` be the closure.
4. If the current node runner's context is an address context,
   allocate the closure in memory and let `result` be its pointer.
5. Finish this expression with `result`.

(There are plans to provide a way to capture free variables that are
 mutable or to capture a variable's value.)


### <a name="index"></a> Index

```
<expression> ::= <expression> [ <expression> ]
```

1. Schedule the first `expression` in a value context with duplication
   requesting 50% of its permission.  Let `aggregate` be the result.
   
2. Schedule the second `expression` in a value context with
   duplication requesting 50% of its permission.  Let `index` be the
   result, which must be an integer.
   
3. If the current node runner's context is a value context
   with duplication, let `result` be a duplicate at 100%
   of the value at the `index` of the tuple.
   Without duplication, let `result` be the value at the `index` of
   the tuple.
   
4. If the current node runner's context is an address context, let
   `result` be the *element address* of the `aggregate` at the
   `index`.
   
5. Finish this expression with `result`.


### <a name="integer"></a>Integer Literal

```
<expression> ::= <integer>
```

1. If the current node runner's context is a value context, let
   `result` be the `integer`.
   
2. If the current node runner's context is an address context,
   allocate the `integer` in memory and let `result` be the allocated
   pointer.

3. Finish this expression with `result`.

### <a name="member"></a>Member Access

```
<expression> ::= <expression> . <identifier>
```

1. Schedule `expression` in address context with duplication,
   requesting 50% of its permission.
   
2. Read from the resulting pointer, which must produce a module value.
   If `identifier` is not a name exported by the module, halt with an error.
   Otherwise, let `ptr` be the associated pointer for the `identifier`
   in the module's exports.
   
3. If the current node runner's context is a value context,
   let `result` be the value of reading `ptr` from memory with
   the runner's context.

4. If the current node runner's context is an address context, and if
   the context is with duplication, let `result` be a duplicate of
   `ptr` taking the percentage specified in the node runner's context.
   If the context is without duplicatoin, let `result` be `ptr`.
   
5. Finish this expression with `result`.

### <a name="null"></a>Null Pointer Literal

```
<expression> ::= null
```

UNDER CONSTRUCTION

### <a name="primitive"></a>Primitive Call

```
<expression> ::= <prim-op> ( <expression_list> )
```

UNDER CONSTRUCTION

### <a name="true"></a>True Literal

```
<expression> ::= true
```

(Similar to the case for [integer literals](#integer).)

### <a name="tuple"></a>Tuple Creation

```
<expression> ::= ⟨ <initializer_list> ⟩
```

1. Schedule each `initializer` (left-to-right) in a value context
   with duplication requesting 50% permission.
   
2. Create a tuple value whose elements are duplicates (at 100%)
   of the results of the initializers.
   
3. If the current node runner's context is a value context, 
   let `result` be the tuple.
   
4. If the current node runner's context is an address context, 
   allocate the tuple in memory and let `result` be a pointer
   to that memory.

5. Finish this expression with `result`.

### <a name="variable"></a>Variable (Occurence)

```
<expression> ::= <identifier>
```

1. If the identifier is not in the current environment, halt with an
   error.

2. If the current runner's context is a value context, read from
   memory using the identifier's address (from the current
   environment) according to the current runner's context.

3. Otherwise the current runner's context is an address context.  If
   it is with duplication, then let `result` be a duplicate the
   identifier's address (from the current environment) at 100%. If the
   context is without duplication, then the `result` is the
   identifier's address (from the current environment).
   
4. Instruct the machine to finish this expression with the `result`.


### <a name="spawn"></a>Spawn a Future

```
<expression> ::= spawn <expression>
```

Evaluate the `expression` in a new thread, concurrent with the current thread.
Immediately returns a *future* associated with the new thread.
This *future* can later be passed to `wait` (see below the description for `await`).

### <a name="wait"></a>Wait on a Future

```
<expression> ::= wait <expression>
```

The `expression` evaluates to a *future*, then the current thread
blocks until the future's thread is finished. The result of this
`wait` is the result of the future's thread.

