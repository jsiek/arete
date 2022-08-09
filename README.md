# Arete

Arete is an experimental programming language.

Some of the features that it will explore are:

* parallelism (currently via futures)

* controlled mutability for data-race freedom, memory safety, etc.
  using both static and dynamic uses of fractional permissions
  
* semi-automatic memory management via fractional permissions
  
* gradual typing

* generics with contraints

* modules

The design of Arete is currently captured in a prototype
implementation written in Python 3.10 that includes:

* grammar and parser ([Arete.lark](Arete.lark) and [parser.py](parser.py))
  using the [Lark](https://github.com/lark-parser/lark) parser generater.

* constant evaluation ([const_eval.py](const_eval.py))

* type checking ([type_check.py](type_check.py))

* desugaring ([desugar.py](desugar.py))

* interpreting (an abstract machine) ([machine.py](machine.py))


The following describes the current status of Arete.

# Value Catalog

A *value* is the runtime object produced by an expression during
program execution. The kinds of values in Arete are listed below.

The values are defined in [values.py](values.py).

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

If the value at `address` in memory is a tuple, then the `path`
specifies which part of the tuple this pointer is referring to.
The path is a list and not just a single integer because tuples
can be nested. So, for example, the path `[3,2]` refers to
the value `12` in the tuple `⟨0,1,2,⟨10,11,12,13⟩,4,5⟩`.

A pointer whose `permission` is `0` or greater can be copied.
A pointer whose `permission` is greater than `0` can be used for
reading.
A pointer whose `permission` is `1` can be used for writing.

If the pointer is a copy of another pointer, then its `lender` is that
other pointer.

## Closures

A closure includes information from the originating function (name,
parameters, body, etc.) and a dictionary mapping the names of its free
variables to pointers.

## Futures

A *future* has an associated thread. 

## Modules

A module has a name, a dictionary of exported members, and a dictionary
of all its members.


# Machine Description

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

Each *frame* has a stack of *node runners*.

A *node runner* is responsible for executing one node in the abstract
syntax tree of the program. Think of each node runner as a little
state machine. Each `NodeRunner` has

* `ast` (the AST node)

* `state` an integer to indicate how far along it is in executing
   this AST node.
   
* `results` a list of value-context pairs, where the values are the
   results of the subexpressions of this AST node. The contexts
   are the contexts under which each subexpression was evaluated.
   (More about contexts below.)
   
* `context` specifies whether the expression should be evaluated for
   its value (aka. rvalue) via `ValueCtx` or its address (aka. lvalue)
   via `AddressCtx`. The context also specifies what percentage of its
   permission is being requested.

* `return_value` is to propagate the result of a `return` statement.

* `return_mode` (the strings `value` or `address`) is whether the enclosing
  function expects to return a value or address.

* `env` a dictionary mapping all the in-scope variables to their addresses.


# Language Feature Catalog

This catalog is organized according to the grammar of the language,
which has three main categories: expressions, statements, and
definitions. Within each category, the entries are ordered
alphabetically.

A program is a list of zero or more definitions:

```
<definition_list> ::=   | <definition> <definition_list>
```

Program execution begins with a call to a function named `main` with
no arguments. If there is no such function, the program halts with an
error.

## Definitions

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

## Statements 

### Assert

```
<statement> ::= assert <expression>;
```

Evaluate the `expression` and halt the program if the result is `false`.

### Assignment

```
<statement> ::= <expression> = <initializer>;
```

### Block

```
<statement> ::= { <statement_list> }
```

### Expression

```
<statement> ::= ! <expression>;
```

Evaluate the `expression` for its effects and discard the result.

### If

```
<statement> ::= if (<expression>) <block>
<statement> ::= if (<expression>) <block> else <block>
```

### Local Variable

```
<statement> ::= let <parameter> = <initializer>;
```

```
<statement> ::= var <identifier> = <expressions>;
```


### Return

```
<statement> ::= return <expression>;
```

### Transfer Permission

```
<statement> ::= <expression> <- <expression> of <expression>
```




### While

```
<statement> ::= while (<expression>) <block>
```

Repeatedly execute the `block` so long as the `expression` evaluates to `true`.


## Expressions

### Spawn

```
<expression> ::= spawn <expression>
```

Evaluate the `expression` in a new thread, concurrent with the current thread.
Immediately returns a *future* associated with the new thread.
This *future* can later be passed to `wait` (see below the description for `await`).

### Wait

```
<expression> ::= wait <expression>
```

The `expression` evaluates to a *future*, then the current thread
blocks until the future's thread is finished. The result of this
`wait` is the result of the future's thread.

