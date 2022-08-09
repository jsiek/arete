# arete

Arete is an experimental programming language.

Some of the features that it will explore are:

* parallelism
* controlled mutability for data-race freedom, memory safety, etc.
  pointers track their permission: none (0), read (1/2, etc.), write (1)
* gradual typing
* generics with contraints
* modules


# Value Catalog

# Machine

# Language Feature Catalog

This catalog is organized according to the grammar of the language,
which has three main categories: expressions, statements, and
definitions. Within each category, the entries are ordered
alphabetically.

Syntactically, a program is a list of zero or more definitions:

```
<definition_list> ::=   | <definition> <definition_list>
```

Semantically, a program must include at least one definition, for the
`main` function.

## Definitions

### Constant

```
const <identifier> [: <type>] = <expression>;
```

### Import

```
from <expression> import <identifier_list>;
```

### Function

```
fun <identifier> (<parameter_list>) [-> <type>] [<return_mode>] <block>
```

### Module

```
module <identifier> exports <identifier_list> { <definition_list> }
```

### Type Alias

```
type <identifier> = <type>;
```

### Variable

```
let <identifier> [: <type>] = <expression>;
```

## Statements 

### Assert

```
assert <expression>;
```

Evaluate the `expression` and halt the program if the result is `false`.

### Assignment

```
<expression> = <initializer>;
```

### Block

```
{ <statement_list> }
```

### Expression

```
! <expression>;
```

Evaluate the `expression` for its effects and discard the result.

### If

```
if (<expression>) <block>
if (<expression>) <block> else <block>
```

### Local Variable

```
let <parameter> = <initializer>;
```

```
var <identifier> = <expressions>;
```


### Return

```
return <expression>;
```

### Transfer Permission

```
<expression> <- <expression> of <expression>
```




### While

```
while (<expression>) <block>
```

Repeatedly execute the `block` so long as the `expression` evaluates to `true`.


## Expressions

### Spawn

```
spawn <expression>
```

Evaluate the `expression` in a new thread, concurrent with the current thread.
Immediately returns a *future* associated with the new thread.
This *future* can later be passed to `wait` (see below the description for `await`).

### Wait

```
wait <expression>
```

The `expression` evaluates to a *future*, then the current thread
blocks until the future's thread is finished. The result of this
`wait` is the result of the future's thread.

