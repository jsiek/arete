# Arete

Arete is an experimental programming language. It aspires
to the following design principles:

1. safety: no undefined behavior. All safety errors are either caught
   at compile time or at runtime. For many kinds of errors, the
   programmer can control when they want the checking (that is, Arete
   will provide gradual typing).
  
2. separate compilation: libraries (including generic ones) can be
   separately compiled and linked with applications. This will ensure
   scalable and efficient compilation of applications and libraries
   with large software dependencies.
   
3. efficient runtime: runtime overheads will in general be low and
   under control of the programmer. Memory management is not via
   garbage collection, but is semi-automatic and under programmer
   control.  Specialization/monomorphization of generics will be
   available as a compiler optimization.

4. high power-to-weight ratio: the language will have a relatively low
   number of features, but those features will be powerful and work
   well in combination.

The Arete language is being designed using an incremental
prototype-first approach. The best way to evaluate a language design
is to write and run lots of programs in the new language. The Arete
abstract machine (the prototype) is a low-cost way to precisely
express the language design and to run programs.

Arete currently includes the following features

* parallelism (via futures)

* controlled mutability for data-race freedom, memory safety, etc.
  via dynamic tracking of fractional permissions.
  
* semi-automatic memory management via fractional permissions
  
* gradual typing (but not yet sound gradual typing, which is planned)

* modules

and I plan to add:

* static checking of fractional permissions,

* generics with contraints and lexically scoped implementationns,

* more features for asynchronous and parallel programming.

The design of Arete is currently captured in a prototype
implementation written in Python 3.10 that includes:

* grammar and parser ([Arete.lark](Arete.lark) and [parser.py](parser.py))
  using the [Lark](https://github.com/lark-parser/lark) parser generater.

* constant evaluation ([const_eval.py](const_eval.py))

* type checking ([type_check.py](type_check.py))

* interpreting (an abstract machine) ([machine.py](machine.py))

The design of Arete is based on discussions with Dave Abrahams and
Dimitri Racordon about their Val language and it is influenced by the
design of the Carbon language. The organization of the abstract
machine is based on Carbon Explorer.


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
saying that the pointer (associated with `x`) does not have read
permission.  In Arete, each pointer has a fraction to control whether
it is allowed to read or write. A pointer with positive fraction may
read and a pointer with a fraction of `1` may write.  The pointer
associated with variable `x` starts out with a permission of `1`, but
when we initialize `y` with `x`, all of its permission is transfered
to the new pointer for `y`. So the write to `y` executes successfully,
but the later read of `x` is an error because by that time, `x` has
`0` permission.

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


# Running and Debugging Arete Programs

To run an Arete program, run [machine.py](machine.py) on `python3.10`
with the file name of the Arete program:

    python3.10 ./machine.py <filename>

The result of the program is in the exit code. So the following
shell command will display it:

    echo $?

To debug an Arete program, add the `debug` flag:

    python3.10 ./machine.py <filename> debug
	
The interpreter will process all the definitions and then pause as it is
about to call your `main` function. You can then enter one of the
following single-character debugger commands:

* `f` evaluate until the current AST node is **finished**.

* `n` evaluate to the **next** subexpression, but don't dive into
  function calls.

* `s` **step** to the next subexpression, diving into function calls.

* `d` **dive** into the next function call.

* `e` print the current **environment** (the in-scope variables).
    Each line displays the name of the variable, the contents of the
	variable, and the address (a pointer) of the variable.

* `m` print the machine's **memory**. Each line displays the address
    (an integer) followed by the value stored at that address.

* `g` output a **graphviz** dot file (named `logs/env_mem_nnn.dot`)
      that represents the environment and memory as a graph. You can
      then use [graphviz](https://graphviz.org/) to generate a PDF.

* `v` toggle **verbose** printing

* `q` **quit**

Breakpoints can be inserted by editing the Arete program to add a call
to the `breakpoint()` primitive function. To express a conditional
breakpoint, place the call to `breakpoint()` inside an `if`.


# Specification 

This is the current specification of the Arete language.

**Table of Contents**

* [Overview](#overview)

* [Machine](#machine)

* [Language Features](#features)

    * [Miscellaneous Features](#miscellaneous)
		* [Assert](#assert)
		* [Block](#block)
		* [Expression Statement](#expr) 
		* [If Statement](#ifstmt)
		* [Pass](#pass) (Do Nothing)
		* [Primitive Call](#primitive)
		* [Recursive Type](#recursive_type)
		* [Type Variable Occurence](#rec_type_var)
		* [While Loop](#while)
		
	* [Arrays](#arrays)
        * [Array Creation](#array)
        * [Index](#indexArray) into an Array

	* [Booleans](#booleans)
        * [False Literal](#false)
        * [True Literal](#true)

	* [Functions](#functions)
        * [Function Definition](#function_def)
        * [Function Expression (Lambda)](#lambda)
        * [Call](#call) a Function
		* [Return Statement](#return)

    * [Generics](#generics)

	* [Modules](#modules)
        * [Import](#import)
        * [Member Access](#member)
        * [Module Definition](#module)

	* [Numbers](#numbers)
        * [Integer Literal](#integer)

	* [Pointers](#pointers)
        * [Address Of](#addressof)
        * [Delete](#delete)
        * [Dereference](#deref) a Pointer
        * [Null Pointer Literal](#null)
        * [Transfer](#transfer) Permission
		* [Write (Assignment)](#write)

    * [Threads](#threads)
		* [Spawn](#spawn) a Future
		* [Wait](#wait) on a Future

	* [Tuples](#tuples)
        * [Index](#indexTuple) into a Tuple
        * [Tuple Creation](#tuple)

    * [Variables](#variables)
		* [Binding Statement](#binding_stmt)
		* [Constant Definition](#constant)
		* [Type Alias Definition](#type_alias)
		* [Variable Definition](#global)
		* [Variable Occurrence](#variable)


# <a name="overview"></a>Overview

The Arete language has three main syntactic categories: expressions,
statements, and definitions. At runtime, an expression produces a
*value* (a piece of data). Most statements perform side effects; some
statements associate a value with an identifier. Most definitions
associate a value with an identifier.  A *program* is a sequence of
zero or more definitions:

```
<definition_list> ::=   | <definition> <definition_list>
```

This specification is organized according to major language features,
such as functions, threads, arrays, modules, etc. In the section for
each major language feature, we define its grammar rules, type
checking rules, and runtime behavior.

In this document we give simplified grammar rules for the language,
that for example, leave out the encoding of precedence. For the exact
grammar rules, see [Arete.lark](Arete.lark). The parser for Arete
produces an abstract syntax tree (AST) where each node is represented
by a Python object. The class definitions for these objects are
organized according to language feature, for example, the `Function`
AST class for representing function definitions is defined in the file
[`functions.py`](functions.py), along with other AST classes related
to functions, such as `Call` and `Lambda`.

We describe the runtime behavior of an Arete program in terms of a
[machine](#machine). The precise definition of the machine is in
[machine.py](machine.py), and it dispatches to the `step` methods
defined in each AST class. So the precise specification of the runtime
behavior of each language feature is given by the `step` method of the
corresponding Python class.

Program execution begins by invoking the `declare` method on every
definition.  For most definitions, this allocates an empty cell in
memory and associates the name of the definition with its
address. (See the `declare` method of the `Decl` base class in
[`ast_base.py`](ast_base.py).) Exceptions to this behavior are
discussed with the description of the particular kind of
definition. The primary purpose of this first phase is to enable
recursive definitions.

The machine then proceeds to interpret each definition by invoking its
`step` method.

Once all the definitions have been interpreted, the machine calls the
function named `main` with no arguments. Once the execution of `main`
is finished, the program exits with the return value of `main`,
provided the machine's memory is empty. If the memory is non-empty,
then the program halts with an error.

# <a name="machine"></a>Machine Description

The *machine* has

* `memory` that maps an address (integer) to a value,

* collection of `threads` including the `current_thread`
  and the `main_thread`.

* `return_value` which eventually holds the value returned by the `main`
  function.

Each *thread* has

* `stack` of *frames* (the procedure call stack), 
  with one *frame* for each function call.
* `return_value` which eventually holds the value produced by the thread.
* `parent` the thread that spawned this thread (optional).
* `num_children` the number of threads spawned by this thread that
    are still running.

Each *frame* has a stack named `todo` of *node runners*.

A *node runner* is responsible for executing one node in the abstract
syntax tree of the program. Think of each node runner as a little
state machine. (It's named "node runner" because I enjoyed playing the
[Lode Runner](https://loderunnerwebgame.com/game/) video game in the
1980's.)  Each node runner has

* `ast` (the AST node)

* `state` an integer to indicate how far along the node runner is in
   executing this AST node.
   
* `results` a list of results for the subexpressions of this AST node.
   Each *result* consists of a value and a Boolean flag that says
   whether the value was newly created by the expression (it is a
   temporary) or not.
   
* `context` specifies whether the expression should be evaluated for
   its value (aka. rvalue) via `ValueCtx` or its address (aka. lvalue)
   via `AddressCtx`. The context also specifies whether to `duplicate` the
   result value (the default is yes, duplicate the pointer).

* `return_value` is to propagate the value from a `return` statement.

* `return_mode` (the strings `value` or `address`) is whether the enclosing
  function expects to return a value or address.

* `env` an *environment*, that is, a dictionary that maps all the
  in-scope variables to their addresses.

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

Inputs: result 

1. Kill all the temporary values in the `results` of the current runner.
   
2. Pop the current runner from the `todo` stack of the current frame.

3. If the `todo` stack of the current frame is not empty, push the
   `result` onto the `results` of the current node runner.

4. Otherwise, if the `stack` of the current thread is not empty, pop
   the current frame from the `stack` and then set the `return_value`
   of the current runner to the value of the `result`.
   
5. Otherwise, set the `return_value` of the current thread to the
   value of the `result`.


### Finish Statement

1. Let `val` be the `return_value` of the current runner.

2. Kill all the temporary values in the `results` of the current runner.

3. Pop the current runner from the `todo` stack of the current frame.

4. If the `todo` stack of the current frame is not empty, 
   set the `return_value` of the current runner to `val`.

5. Otherwise, if the `stack` of the current thread is not empty, pop
   the current frame from the `stack` and then set the `return_value`
   of the current runner to `val`.
   
6. Otherwise, set the `return_value` of the current thread to the `val`.


### Finish Definition

1. Kill all the temporary values in the `results` of the current runner.

2. Pop the current runner from the `todo` stack of the current frame.


### <a name="bind_param"></a>Bind a Parameter

Inputs: `parameter`, `result`, `environment`

1. If the value of the `result` is not a pointer or pointer offset,
   halt with an error.
   
2. If the `result` is a temporary, update the `environment` to
   associate the parameter's identifier with the value of the
   `result`.

3. If the `parameter` is a `let` do the following:

    a. If the `address` of the pointer is `None` or its permission is
	   `0`, halt with an error.
	   
    b. If the `result` is not a temporary, update the `environment` to
	   associate the parameter's identifier with a duplicate of the
	   value of the result, taking 50% of its permission.
	   
4. Otherwise, if the `parameter` is a `var` or `inout`, do the following:

    a. If the `address` of the pointer is `None` or its permission is
	   not `1`, halt with an error.
	   
    b. If the `result` is not a temporary, update the `environment` to
	   associate the parameter's identifier with a duplicate of the
	   value of the result, taking 100% of its permission.
	   
    c. If the `parameter` is a `var`, set the `no_give_backs` flag to
	   true on the pointer that just added to the `environment`.

5. Otherwise, if the `parameter` is a `ref` and `result` is not a
   temporary, update the `environment` to associate the parameter's
   identifier with a duplicate of the value of the result, taking 100%
   of its permission.

### <a name="dealloc_param"></a>Deallocate a Parameter

Inputs: parameter, argument value, environment

1. Let `ptr` be the value associated with the parameter's
   identifier in the given environment.

2. If the `parameter` is `inout`, do the following:

    a. If the permission of `ptr` is not `1`, halt with an error.n
	
	b. If the argument value is not live, halt with an error.
	
	c. Transfer all of the permission from `ptr` to the argument value.

3. Kill the `ptr`.


## Memory Operations

### <a name="read_op"></a>Read

Inputs: pointer

1. If the pointer has `0` permission, halt with an error.

2. Obtain the value `val` at the pointer's `address` in memory.
   Process the `val` and the pointer's `path` recursively as follows.
   
    * If the `path` is an empty list, then return `val`.
	
    * If the `path` is non-empty, check that `val` is a tuple
      and halt with an error if not. Recusively process the
      `i`th element of `val` (where `i` is `path[0]`) with `path[1:]`.

### <a name="write_op"></a>Write

Inputs: pointer, value

1. If the pointer does not have `1` permission, halt with an error.

2. Let `old_val` be the value obtained by reading from memory with
   the given pointer (see the above Read operation).
   
3. Let `val_copy` be a duplicate of the input value.

4. Update the location in memory for the pointer's address with a new
   whole value obtained by splicing `val_copy` into the place where
   `old_val` was in the old whole value at the pointer's `address`.
   To be precise, recursively process the value at the pointer's
   `address` (call it `val`) and the pointer's `path` as follows to
   produce a new value as follows.
   
   * If the `path` is an empty list, then `val_copy` is the new value.
	 
   * If the `path` is non-empty, check that `val` is a tuple and halt
     with an error if not. Recursively process the `i`th element of
     `val` (where `i` is `path[0]`) with `path[1:]` to obtain
     `new_val`. The new value is then constructed by creating a tuple
     whose elements are obtained by concatenating `val.elts[:i]`, the
     `new_val`, and `val.elts[i+1:]`.


### Deallocate

Inputs: address

1. Kill the value that is in memory at the given address.

2. Delete the entry for this address in the memory.



# <a name="features"></a>Language Features

## <a name="miscellaneous"></a> Miscellaneous Features

### <a name="assert"></a>Assert

```
<statement> ::= assert <expression>;
```

#### Type Checking

The type of `expression` must be consistent with `bool`.

#### Step

1. Schedule the `expression` in the current environment with value
   context and duplication.

2. If the result is `false`, halt with an error.

3. Otherwise, finish this statement.


### <a name="block"></a>Block

```
<statement> ::= { <statement_list> }
```

#### Type Checking

Perform type checking on each statement in the block.

#### Step

1. Schedule the body in the current environment.

2. Finish this statement.

### <a name="expr"></a>Expression Statement

```
<statement> ::= <expression>;
```

#### Type Checking

Perform type checking on the `expression`.

#### Step

1. Schedule the `expression` in the current environment with value
   context and duplication.

2. Finish this statement.


### <a name="ifstmt"></a>If Statement

```
<statement> ::= if (<expression>) <block>
<statement> ::= if (<expression>) <block> else <block>
```

The one-armed `if` is parsed into a two-armed `if` whose
else branch is a [Pass](#pass) statement.

#### Type Checking

The type of `expression` must be consistent with `bool`.

Perform type checking on the branches.


#### Step

To interpret a two-armed `if`: 

1. Schedule the condition `expression` in the current environment with
   value context and duplication.

2. If the result is true, schedule the then branch.

3. Otherwise, if the result is false, schedule the else branch.

4. Finish this statement.



### <a name="pass"></a>Pass (Do Nothing)

#### Step

1. Finish this statement.

### <a name="primitive"></a>Primitive Call

```
<expression> ::= <prim-op> ( <expression_list> )
```

#### Type Checking

See the `type_check_prim` function in
[`primitive_operations.py`](primitive_operations.py).

#### Step

1. Schedule each argument `expression`.

2. Compute the result value according to the function `eval_prim`
   in [primitive_operations.py](primitive_operations.py) with
   the argument results and the `prim-op`.

3. If the current runner's context is address context, allocate the
   result value in memory and let `result` be the new pointer. (A
   temporary). Otherwise, we're in value context and let `result` be
   the result value. (Also a temporary.)


### <a name="recursive_type"></a>Recursive Type

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

(Recursive types are unweildy to deal with directly, so the plan is to
add syntactic sugar for them.)


### <a name="rec_type_var"></a>Type Variable Occurence

```
<type> ::= <identifier>
```

An occurence of a type variable may refer to a recursive type.
(See the entry for [Recursive Type](#recursive_type).)

### <a name="while"></a>While Loop

```
<statement> ::= while (<expression>) <block>
```

#### Type Checking

The type of `expression` must be consistent with `bool`.

#### Step

1. Schedule the condition `expression` in the current environment
   with value context and duplication.
   
2. If the result of the condition is true, schedule this `while`
   statement again and then schedule the `block`. (We schedule the
   `block` after this `while` statement because the machine treats the
   `todo` list as a stack, that is, in last-in-first-out order.)

3. Finish this statement.




## <a name="variables"></a> Variables

There are several auxiliary grammar rules related to variable and
parameter definitions.

```
<parameter> ::= <binding_kind> <identifier> [: <type>]
```

The `parameter` category is used for function parameters and variable
definitions (e.g. the `let` statement). If no type annotation is
present, the parameter is given the unknown type `?`.

```
<binding_kind> ::=   | let | var | inout | ref
```

If no binding kind is specified, it defaults to `let`.

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

### <a name="constant"></a>Constant

```
<definition> ::= const <identifier> [: <type>] = <expression>;
```

#### Type Checking

UNDER CONSTRUCTION

#### Constant Evaluation (compile-time)

The occurences of `identifier` in the program are replaced by the
result of evaluating `expression`. (See
[const_eval.py](const_eval.py).)

#### Step

1. Finish this declaration.


### <a name="type_alias"></a>Type Alias

```
<definition> ::= type <identifier> = <type>;
```

#### Type Checking

The result of simplifying `type` is associated with `identifier` in
the type environment.

#### Step

1. Finish this declaration.

### <a name="global"></a>Variable Definition

```
<definition> ::= let <identifier> [: <type>] = <expression>;
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule the `expression` in a value context with duplication.

2. Write the resulting value to memory using the pointer associated
   with `identifier` in the current environment.
   
3. Finish this definition.


### <a name="binding_stmt"></a>Binding Statement (Let, Var, etc.)

```
<statement> ::= <parameter> = <expression>; <statement_list>
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule the `expression` in the current environment with address
   context and duplication.

2. Copy the current environment and name it `body_env`.
   
3. [Bind](#bind_param) the result from `expression` to the parameter
   in the `body_env`.
   
4. Schedule the following `statement_list` in the environment `body_env`.

6. Once the `statement_list` is finished, 
   [deallocate the parameter](#dealloc_param) with the result
   from the `expression` and the `body_env`.
   
7. Finish this statement.
   
### <a name="variable"></a>Variable Occurence

```
<expression> ::= <identifier>
```

#### Type Checking

Check that the identifier is in the static environment to obtain its
static `info` and report a static error if it is not.

If the context is a `let` binding, then check that the `info` state is
readable and report a static error if it is not. Update the `info`
state to be a proper fraction and add this identifier to the current
set of borrowed variables.

If the context is an `inout` binding, then check that the `info` state
is a full fraction and report a static error if it is not. Update the
`info` state to be an empty fraction and add this identifier to the
current set of borrowed variables.

If the context is `var` binding, then check that the `info` state is a
full fraction and report a static error if it is not. Update the
`info` state to be dead.

If the context is a `ref` binding, UNDER CONSTRUCTION

If the context is the left-hand side of an assignment statement, check
that the `info` state is a full fraction and report a static error if
it is not. 

If the context is the right-hand side of an assignment statement,
check that the `info` state is readable and report a static error if
it is not.

The type of this identifier is the `type` field of `info`.

The translation is the `translation` field of `info` unless it is
`None`, in which case the translation is this identifier.


#### Step

1. If the identifier is not in the current environment, halt with an
   error.

2. If the current runner's context is a value context, read from
   memory using the identifier's pointer (from the current
   environment). If the current runner's context requests duplication,
   let `result` be a duplicate of the value in memory, taking the
   percentage specified by the identifier's pointer. (A temporary.)
   Otherwise, let `result` be the value in memory. (Not a temporary.)

3. Otherwise the current runner's context is an address context.
   Return the identifier's pointer. (Not a temporary).
   
4. Instruct the machine to finish this expression with the `result`.


## <a name="arrays"></a> Arrays

```
<type> ::= [ <type> ]
```

### <a name="array"></a>Array Creation

```
<expression> ::= [ <expression> of <expression> ]
```

#### Example

The following program creates an array `a` of length `10` that is
initialized with `0`. It then writes the integers `0` through `9` in
the array and finishes by accessing the last element.

	fun main() {
	  let n = 10;
	  var a = [n of 0];
	  var i = 0;
	  while (i < len(a)) {
		a[i] = i;
		i = i + 1;
	  }
	  let last = a[9];
	  return last - 9;
	}

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule the size `expression` in value context with duplication.
   The result must be a integer, call it `n`.

2. Schedule the initial `expression` in value context with duplication.

3. Duplicate the initial value `n` times, taking 50% permission each time.
   Create a tuple value whose elements are these duplicates.
   
4. If the current runner's context is value context, let `result`
   be the tuple value. Otherwise, we're in address context,
   so we allocate the tuple value in memory and let `result` be
   the new pointer. In either case, the result is a temporary.

5. Finish this expression with `result`.


### <a name="indexArray"></a> Index into an Array

```
<expression> ::= <expression> [ <expression> ]
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule the first `expression` in the current environemnt 
   in address context with the duplication specified by the current runner.
   Let `ptr` be the result.
   
2. Schedule the second `expression` in a value context with
   duplication.  Let `index` be the result, which must be an integer.
   
3. If the current node runner's context is a value context with
   duplication, let `arr` be the array obtained by reading from memory
   at `ptr`. If `ptr` is a temporary, then let `result` be a duplicate
   of the element at `index` of `arr` (which should also be considered
   a temporary), taking a percentage of the element according to the
   permission of `ptr.  If `ptr` is not a temporary, let `result` be
   the element at `index` of `arr`.

4. If the current node runner's context is an address context, create
   a pointer offset whose offset is `index` and whose underlying
   pointer is either the `ptr` (if it was not a temporary) or a
   duplicate of `ptr` (if it was a temporary). Let `result` be the new
   pointer offeset. We categorize it as temporary if the `ptr` was
   temporary.
   
5. Finish this expression with `result`.


## <a name="booleans"></a> Booleans

The values `true` and `false` have the type `bool`.

```
<type> ::= bool
```

### <a name="false"></a>False Literal

```
<expression> ::= false
```

### <a name="true"></a>True Literal

```
<expression> ::= true
```


## <a name="functions"></a> Functions

A function value (aka. closure) includes information from the
originating function (name, parameters, body, etc.) and the
environment from its point of definition.

A function type includes a list of parameter types and the return type.

```
<type> ::= ( <type_list> ) -> <type>
```

A comma-separated list of types is a `type_list`.

```
<type_list> ::= <type> | <type> , <type_list>
```

### <a name="function_def"></a>Function Definitions

```
<definition> ::= fun <identifier> (<parameter_list>) [-> <type>] [<return_mode>] <block>
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Create a function expression AST node and schedule it in the
   current environment with value context and duplication.
   
2. Write the resulting value to memory at the address associated with
   the function's name in the current environment.

3. Finish this definition.

### <a name="lambda"></a>Function Expression (Lambda)

```
<expression> ::= fun ( <parameter_list> ) <return_mode> <block>
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

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

### <a name="call"></a>Call

```
<expression> ( <initializer_list> )
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule the `expression` in the current environment with value
   context and duplicaton.  The result must be a closure.

2. Schedule each `initializer` (left to right) in the current
   environment with address context and duplication.
   
3. Copy the closure's environment into `body_env`.
   [Bind](#bind_param) each parameter to the corresponding result from
   its initializer.

4. Create a new frame and push it onto the `stack` of the current thread.
   
5. Schedule the body of the closure with the environment `body_env`
   and the closure's return mode.

6. Upon completion of the body, [deallocate](#dealloc_param) each
   parameter.  If the current node runner's `return_value` is `None`,
   set it to the void value.
   
     a. If the current node runner's context is a value context, and
        its return mode is `value`, let `result` be the runner's
        `return_value`.  If the runner's return mode is `address`,
        then the runner's `return_value` is a pointer; let `result` be
        the value read from memory at that pointer.  Kill the pointer.

     b. If the current node runner's context is a address context, and
	    its return mode is `value`, allocate the runner's `return_value`
		in memory and let `result` be the new address.
		If the return mode is `address`, let `result` be the 
        runner's `return_value`.

7. Finish this expression with `result`.


### <a name="return"></a>Return Statement

```
<statement> ::= return <expression>;
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule the `expression` in the current environment with
   duplication using value or address context as specified by the
   `return_mode` of the current node runner.

2. Set the `return_value` of the current node runner to a duplicate
   (at 100%) of the expression's result.

3. Finish this statement.


## <a name="generics"></a> Generics

UNDER CONSTRUCTION

## <a name="gradual"></a> Gradual Typing

### The Unknown Type (aka. the "any" type or the "dynamic" type)

```
<type> ::= ?
```

This type enables gradual typing because an expression of unkown type
`?` may produce any type of runtime value.


### Type Variable Occurrence

```
<type> ::= <identifier>
```

An occurence of a type variable may refer to a type parameter of a
generic entity.



## <a name="modules"></a> Modules

A module has a name, an environment of exported members, and an
environment of all its members. Modules are compile-time entities,
they are not (runtime) values.


### <a name="import"></a>Import

```
<definition> ::= from <expression> import <identifier_list>;
```

#### Type Checking

UNDER CONSTRUCTION

#### Declare

The `declare` method of an import allocates an empty cell in memory
for each name being imported, and associates the name with the cell's
address in the current environment.

#### Step

1. Schedule the `expression` in the current environment with address context
  and duplication.
  
2. Read from memory at the resulting pointer, which must produce a module. 
   For each of the names in the `identifier_list` of the import, 
   check whether it is in the module's exports and halt with an error
   if it is not. Otherwise, read from memory using the pointer associated
   with the name in the export environment of the module. Then duplicate
   the value, taking the percentage of the pointer's permission.
   Write the duplicated value to memory, using the pointer associated
   with the name in the current environment.
   
3. Finish this definition.


### <a name="member"></a>Member Access

```
<expression> ::= <expression> . <identifier>
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule `expression` in the current environment with address
   context with duplication.
   
2. Read from the resulting pointer, which must produce a module value.
   If `identifier` is not a name exported by the module, halt with an error.
   Otherwise, let `ptr` be the associated pointer for the `identifier`
   in the module's exports.
   
3. If the current node runner's context is a value context, let
   `result` be a duplicate of the value at `ptr` in memory, taking a
   percentage according to the permission of `ptr`. Categorize this
   result as a temporary.

4. If the current node runner's context is an address context, let
   `result` be `ptr`. (Not a temporary.)
   
5. Finish this expression with `result`.

### <a name="module"></a>Module Definition

```
<definition> ::= module <identifier> exports <identifier_list> { <definition_list> }
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Let `body_env` be a new empty environment.

2. Invoke the `declare` method on each definition in the module,
   with the `body_env`.
   
3. Schedule each definition in the module with the `body_env`.

4. For each identifier in the list of exports, check that
   there is an entry in `body_env`.
   
4. Create a module value. It's `exports` environment maps each name in
   the module's export list to the pointer for that name in
   `body_env`. The `members` environment of the module is `body_env`.

5. Write the module value to the address associated with its name in
   the current environment.
   
6. Finish this definition.


## <a name="numbers"></a> Numbers

The numbers currently include integers and rationals.

```
<type> ::= int
```

```
<type> ::= rational
```

### <a name="integer"></a>Integer Literal

```
<expression> ::= <integer>
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. If the current node runner's context is a value context, let
   `result` be the `integer`.
   
2. If the current node runner's context is an address context,
   allocate the `integer` in memory and let `result` be the allocated
   pointer.

3. Finish this expression with `result`.

### <a name="rational"></a>Rational Literal

UNDER CONSTRUCTION


## <a name="pointers"></a> Pointers

A pointer value includes the following fields:

* `address` (an integer)
* `path` (list of integers)
* `permission` (fraction)
* `lender` (another pointer, optional)
* `kill_when_zero` (a Boolean)
* `no_give_backs` (a Boolean)

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
killed when its `permission` reaches zero. This used for `let`
variables.

The if `no_give_backs` flag is set to true, then when the pointer is
killed, it does not give its permissions back to its ender (as it
normally would). This is used for `var` variables.

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
   pointer's permission to the living lender. (Unless the
   `no_give_backs` flag is set to true.)
   
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


### Upgrade

If the pointer has a living lender, transfer all of the lender's
permission to this pointer. Return `true` or `false` corresponding to
whether this pointer's permission is equal to `1`.

### Pointer Offset

We sometimes need to delay the duplication of a pointer when using it
to index into a tuple, which we accomplish with another pointer-like
value called a *pointer offset*, which has the following fields.

* `ptr` (a Pointer)
* `offset` (an integer)

A pointer offset acts like its underlying `ptr` but with the given
`offset` appended to the end of its `path`.



### <a name="addressof"></a>Address Of

```
<expression> ::= & <expression>
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule `expression` in the current environment with address
   context with duplication.
   
2. If the current runner's context is value context, do the following.
   If the result of `expression` was a temporary, duplicate it
   and set `result` to the duplicate as a new temporary.
   If the result of `expression` was not temporary, 
   set `result` to the result of `expression`.
    
3. Otherwise, if the current runner's context is address context,
   allocate the result's value in memory and set `result` to
   the new pointer (it's a temporary).

4. Finish this expression with `result`.

### <a name="delete"></a>Delete

```
<statement> ::= delete <expression>;
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule the `expression` in the current environment with value
   context and duplication.  The result must be a pointer.

2. Deallocate the memory associated with the pointer,
   set its `address` to `None` and its permission to `0`.

3. Finish this statement.


### <a name="deref"></a>Dereference a Pointer

```
<expression> ::= * <expression>
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule the `expression` in value context and with the current
   runner's duplication. The result must be a pointer
   
2. If we're in value context, read from memory at the pointer and
   duplicate it, taking the percentage according to the permission of
   the pointer. Let `result` be the duplicate. (It's a temporary.)
   
3. Otherwise, we're in address context. If the pointer is a temporary,
   let `result` be a duplicate of it. Otherwise let `result` be the pointer.
   
4. Finish this expression with `result`.

### <a name="null"></a>Null Pointer Literal

```
<expression> ::= null
```

This is parsed as a call to a primitive function named `null`.


### <a name="transfer"></a>Transfer Permission

```
<statement> ::= <expression> <- <expression> of <expression>
```

Let `amount` be the permission of the source pointer multiplied by the
given percentage.  Decrease the permission of the source pointer by
`amount` and increase the permission of this pointer by `amount`.  If
the permission of the source pointer becomes `0` and its
`kill_when_zero` flag is true, then kill it.

### <a name="write"></a>Write (Assignment)

```
<statement> ::= <expression> = <initializer>;
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule the `initializer` in the current environment with value
  context and duplication.
  
2. Schedule the `expression` in the current environment with address
  context and duplication. The result must be a pointer.

3. [Write](#write_op) the result of the initializer to the pointer.

4. Finish this statement.

(The order of evaluation here does not follow our usual left-to-right
 policy. Using left-to-right for assignment triggers errors in many of
 our test cases. I have not yet investigated why this is.)


#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule the target `expression` in the current environment with
   value context and without duplication. The result value must be a
   pointer.
   
2. Schedule the percentage `expression` in the current environment
   with value context and duplication. The result value must be a
   rational number.
   
3. Schedule the source `expression` in the current environment with
   value context and without duplication. The result value must be a
   pointer.

4. Transfer the given percent from the source pointer to the target
   pointer.
   
5. Finish this statement.



## <a name="threads"></a> Threads

A *future* value has an associated thread. 

### <a name="spawn"></a>Spawn a Future

```
<expression> ::= spawn <expression>
```

Evaluate the `expression` in a new thread, concurrent with the current
thread.  Immediately returns a *future* associated with the new
thread.  This *future* can later be passed to `wait` (see below the
description for `await`).

#### Type Checking

UNDER CONSTRUCTION

#### Step

Inputs: an expression and environment

1. Create a node runner with the given expression and environment,
   with a value context and the same return mode as the current runner.
   
2. Create a new frame whose `todo` list just includes the new runner.

3. Increment the `num_children` of this thread.

4. Create a new thread whose `stack` just includes the new frame
   and whose `parent` is the current thread.
   
5. Append the new thread to the `threads` of the machine.

6. Return a new future associated with the new thread.

### <a name="wait"></a>Wait on a Future

```
<expression> ::= wait <expression>
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

The `expression` evaluates to a *future*, then the current thread
blocks until the future's thread is finished. The result of this
`wait` is the result of the future's thread.



## <a name="tuples"></a> Tuples

A tuple is a value that contains a sequence of values called its
elements. The elements of a tuple can be accessed with zero-based
indexing.

The following tuple contains six values, and the element at index 3 is
another tuple.

```
⟨3,true,2,⟨10,false,12,13⟩,4,5⟩
```

```
<type> ::= ⟨ <type_list> ⟩
```

TODO: discuss the operations on tuples.


### <a name="tuple"></a>Tuple Creation

```
<expression> ::= ⟨ <initializer_list> ⟩
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule each `initializer` (left-to-right) in the current
   environment with value context with duplication.
   
2. Create a tuple value whose elements are duplicates (at 100%)
   of the results of the initializers.
   
3. If the current node runner's context is a value context, 
   let `result` be the tuple. (A temporary.)
   
4. If the current node runner's context is an address context, 
   allocate the tuple in memory and let `result` be a pointer
   to that memory. (A temporary.)

5. Finish this expression with `result`.

### <a name="indexTuple"></a> Index into a Tuple

```
<expression> ::= <expression> [ <expression> ]
```

#### Type Checking

UNDER CONSTRUCTION

#### Step

1. Schedule the first `expression` in the current environemnt 
   in address context with the duplication specified by the current runner.
   Let `ptr` be the result.
   
2. Schedule the second `expression` in a value context with
   duplication.  Let `index` be the result, which must be an integer.
   
3. If the current node runner's context is a value context with
   duplication, let `tup` be the tuple obtained by reading from memory
   at `ptr`. If `ptr` is a temporary, then let `result` be a duplicate
   of the element at `index` of `tup` (which should also be considered
   a temporary), taking a percentage of the element according to the
   permission of `ptr.  If `ptr` is not a temporary, let `result` be
   the element at `index` of `tup`.

4. If the current node runner's context is an address context, create
   a pointer offset whose offset is `index` and whose underlying
   pointer is either the `ptr` (if it was not a temporary) or a
   duplicate of `ptr` (if it was a temporary). Let `result` be the new
   pointer offeset. We categorize it as temporary if the `ptr` was
   temporary.
   
5. Finish this expression with `result`.



# TODO

[X] Add variants. (safe unions)
[X] Remove null pointers.
[X] Refactor type-check into AST methods
[X] interfaces, impls, and constraints
[ ] adding type checking descriptions to the spec
[ ] add variants to the spec
[ ] Explicit type arguments for generic functions.
[ ] Make the `as T` part of the `tag` expression optional.
[ ] debugger: command to display the stack (like backtrace in gdb)
[ ] Refactor desugar, const-eval into AST methods
[ ] Test cases for type checking failures.
[ ] generic impls
[ ] Check whether the pointer "lender" logic is no longer needed
