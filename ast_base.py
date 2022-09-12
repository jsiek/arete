from __future__ import annotations # To refer to class type in the class.

from dataclasses import dataclass
from lark.tree import Meta
from typing import Any

@dataclass
class Value:
  def node_name(self):
    return str(self)
  
  def node_label(self):
    return str(self)

  def get_subobject(self, path, loc):
    if len(path) == 0:
      return self
    else:
      error(loc, 'in get_subobject, this value has no sub-parts: ' + str(self))

  def set_subobject(self, path, val, loc):
    if len(path) == 0:
      return val
    else:
      error(loc, 'in set_subobject, this value has no sub-parts: ' + str(self))
      
  def gen_graphviz(self, addr):
    if addr is None:
      return '', None, self.node_label()
    else:
      graph = str(addr) + ' [shape=record,label="' \
             + '<base> ' + str(addr) + ': |' \
             + self.node_label() \
             + '"];\n'
      return graph, str(addr), self.node_label()

@dataclass
class Void(Value):
  def kill(self, mem, loc, progress=set()):
    pass
  def clear(self, mem, loc, progress=set()):
    pass
  def duplicate(self, percentage, location):
    pass

@dataclass
class AST:
    location: Meta
    
    def debug_skip(self):
      return False

@dataclass(frozen=True)
class Type:
    location: Meta
    def copy(self):
      return self

@dataclass
class Exp(AST):
  
  def __str__(self):
    raise Exception('unimplemented')
  
  def __repr__(self):
    raise Exception('unimplemented')

  # Returns the set of free variables of this expression.
  def free_vars(self) -> set[str]:
    raise Exception('unimplemented')

  # Checks that the expression obeys the type checking rules.
  # The environment `env` provides the types for all of the
  # variables that are currently in scope.
  # Returns the type of this expression and a translation
  # of this expression.
  def type_check(self, env: dict[str,Type]) -> tuple[Type,Exp]:
    raise Exception('unimplemented')

  # Takes one small step of runtime execution of this expression.
  # The `runner` parameter is an instance of `NodeRunner` that
  # contains the state needed for the execution of this expression.
  # The `machine` parameter is the sole instance of `Machine`.
  def step(self, runner, machine):
    raise Exception('unimplemented')
  

@dataclass
class Stmt(AST):

  def __str__(self):
    raise Exception('unimplemented')

  def __repr__(self):
    raise Exception('unimplemented')

  # Returns the set of free variables of this statement.
  def free_vars(self) -> set[str]:
    raise Exception('unimplemented')

  # Checks that the statement obeys the type checking rules.
  # The environment `env` provides the types for all of the
  # variables that are currently in scope.
  # Returns the type of any return expressions contained in this
  # expression (or None) and returns a translation of this statement.
  def type_check(self, env: dict[str,Type]) -> tuple[Type,Stmt]:
    raise Exception('unimplemented')
  
  # Takes one small step of runtime execution of this statement.
  # The `runner` parameter is an instance of `NodeRunner` that
  # contains the state needed for the execution of this expression.
  # The `machine` parameter is the sole instance of `Machine`.
  def step(self, runner, machine):
    raise Exception('unimplemented')


# TODO: change name of Decl to Definition
@dataclass
class Decl(AST):
  
  def __str__(self):
    raise Exception('unimplemented')
    
  def __repr__(self):
    raise Exception('unimplemented')

  def free_vars(self) -> set[str]:
    raise Exception('unimplemented')

  # Evaluate compile-time constants and type expressions,
  # producing a new version of this definition.
  def const_eval(self, env: dict[str,Any]) -> list[Decl]:
    raise Exception('unimplemented')
  
  # Declares the names and types associated with this definition.
  # The `env` parameter maps the in-scope variables to their types.
  # The result is a dictionary mapping names to types and represents
  # the names declared by this definitionn.
  def declare_type(self, env: dict[str,Type]) -> dict[str,Type]:
    raise Exception('unimplemented')
    
  # type_check ensures that the definition obeys the type checking rules.
  # The environment `env` provides the types for all of the variables
  # that are currently in scope. It also provides a translation of the
  # variable, which in most cases is just the variable itself. The
  # environment also maps each interface name to their declaration
  # and impls.
  # type_check returns a translation of this definition.
  def type_check(self, env: dict[str,Any]) -> list[Decl]:
    raise Exception('unimplemented')
      
  def declare(self, env: dict[str,Value], mem):
    env[self.name] = mem.allocate(Void())
    
  def step(self, runner, machine):
    raise Exception('unimplemented')
