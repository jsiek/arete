# Arete

Arete is an experimental programming language.

Some of the features that it will explore are:

* parallelism (currently via futures)

* controlled mutability for data-race freedom, memory safety, etc.

  pointers have a fractional permission: 
    * 0 (none), 
	* between 0 and 1 (read),
	* 1 (write)
  
* gradual typing

* generics with contraints

* modules

The design of Arete is currently captured in a prototype
implementation that includes 
* grammar and parser ([Arete.lark](Arete.lark) and [parser.py](parser.py))
  using the [Lark](https://github.com/lark-parser/lark) parser generater.
* type checker ([type_check.py](type_check.py))
* desugaring ([desugar.py](desugar.py))
* interpreter (an abstract machine) ([machine.py](machine.py))


The following describes the current status of Arete.

# Value Catalog

The values are defined in [values.py](values.py).

## Numbers (integers and fractions)

## Booleans

## Tuples

## Pointers

## Closures

## Futures

## Modules



# Machine Description

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

