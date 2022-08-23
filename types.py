from ast_base import Type

# Types

# Note: we use tuples instead of lists inside types because types need
# to be hashable, so they may only contain immutable values.

@dataclass(eq=True, frozen=True)
class AnyType(Type):
  def __str__(self):
    return '?'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class IntType(Type):
  def __str__(self):
    return 'int'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class RationalType(Type):
  def __str__(self):
    return 'rational'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class BoolType(Type):
  def __str__(self):
    return 'bool'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class VoidType(Type):
  def __str__(self):
    return 'void'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class PointerType(Type):
  type: Type
  __match_args__ = ("type",)
  def __str__(self):
    return str(self.type) + '*'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class RecursiveType(Type):
  name: str
  type: Type
  __match_args__ = ("name", "type",)
  def __str__(self):
    return '(rec ' + self.name + ' in ' + str(self.type) + ')'
  def __repr__(self):
    return str(self)
  
@dataclass(eq=True, frozen=True)
class ArrayType(Type):
  element_type: Type
  __match_args__ = ("element_type",)
  def __str__(self):
    return 'array[' + str(self.element_type) + ']'
  def __repr__(self):
    return str(self)
  
@dataclass(eq=True, frozen=True)
class TupleType(Type):
  member_types: tuple[Type]  
  __match_args__ = ("member_types",)
  def __str__(self):
    return '⟨' + ', '.join([str(t) for t in self.member_types]) + '⟩'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class VariantType(Type):
  alternative_types: tuple[tuple[str,Type]]  
  __match_args__ = ("alternative_types",)
  def __str__(self):
    return '(variant ' + '| '.join([x + ':' + str(t) \
                            for x,t in self.alternative_types]) + ')'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class FunctionType(Type):
  type_params: tuple[str]
  param_types: tuple[Type]
  return_type: Type
  __match_args__ = ("type_params", "param_types", "return_type")
  def __str__(self):
    return ('<' + ', '.join(self.type_params) + '>'
            if len(self.type_params) > 0\
            else '') \
           + '(' + ', '.join([str(t) for t in self.param_types]) + ')' \
           + '->' + str(self.return_type)
  def __repr__(self):
    return str(self)
    
@dataclass(eq=True, frozen=True)
class ModuleType(Type):
  member_types: dict[str, Type]
  __match_args__ = ("member_types",)
  def __str__(self):
    return '{' + ', '.join([n + ':' + str(t) \
                            for n,t in self.member_types.items()]) + '}'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class FutureType(Type):
  result_type: Type
  __match_args__ = ("reult_type",)
  def __str__(self):
    return '^' + str(self.result_type)
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class TypeVar(Type):
    ident: str
    __match_args__ = ("ident",)
    def __str__(self):
        return '`' + self.ident
    def __repr__(self):
        return str(self)
  
