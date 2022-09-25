from dataclasses import dataclass
from ast_base import Type, AST, Exp
from typing import Any
from lark.tree import Meta
from utilities import tracing_on, error

# Types

# Note: we use tuples instead of lists inside types because types need
# to be hashable, so they may only contain immutable values.

@dataclass(eq=True, frozen=True)
class AnyType(Type):
  def __str__(self):
    return '?'
  def __repr__(self):
    return str(self)
  def __eq__(self, other):
    return isinstance(other, AnyType)

@dataclass(eq=True, frozen=True)
class IntType(Type):
  def __str__(self):
    return 'int'
  def __repr__(self):
    return str(self)
  def __eq__(self, other):
    return isinstance(other, IntType)

@dataclass(eq=True, frozen=True)
class RationalType(Type):
  def __str__(self):
    return 'rational'
  def __repr__(self):
    return str(self)
  def __eq__(self, other):
    return isinstance(other, RationalType)

@dataclass(eq=True, frozen=True)
class BoolType(Type):
  def __str__(self):
    return 'bool'
  def __repr__(self):
    return str(self)
  def __eq__(self, other):
    return isinstance(other, BoolType)

@dataclass(eq=True, frozen=True)
class VoidType(Type):
  def __str__(self):
    return 'void'
  def __repr__(self):
    return str(self)
  def __eq__(self, other):
    return isinstance(other, VoidType)

@dataclass(eq=True, frozen=True)
class PointerType(Type):
  type: Type
  __match_args__ = ("type",)
  def __str__(self):
    return str(self.type) + '*'
  def __repr__(self):
    return str(self)
  def __eq__(self, other):
    return isinstance(other, PointerType) and self.type == other.type

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
  def __eq__(self, other):
    return isinstance(other, ArrayType) \
      and self.element_type == other.element_type
  
@dataclass(eq=True, frozen=True)
class TupleType(Type):
  member_types: tuple[Type]  
  __match_args__ = ("member_types",)
  def __str__(self):
    return '⟨' + ', '.join([str(t) for t in self.member_types]) + '⟩'
  def __repr__(self):
    return str(self)
  def __eq__(self, other):
    return isinstance(other, TupleType) \
      and all([t1 == t2 for t1,t2 in zip(self.member_types,
                                         other.member_types)])

@dataclass(eq=True, frozen=True)
class RecordType(Type):
  field_types: tuple[tuple[str,Type]]  
  __match_args__ = ("field_types",)
  def __str__(self):
    return '{' + ', '.join([x + ':' + str(t) \
                            for x,t in self.field_types]) + '}'
  def __repr__(self):
    return str(self)
  def __eq__(self, other):
    # TODO: allow different orderings
    return isinstance(other, RecordType) \
      and all([t1 == t2 for t1,t2 in zip(self.field_types,
                                         other.field_types)])

  
@dataclass(eq=True, frozen=True)
class VariantType(Type):
  alternative_types: tuple[tuple[str,Type]]  
  __match_args__ = ("alternative_types",)
  def __str__(self):
    return '(variant ' + '| '.join([x + ':' + str(t) \
                            for x,t in self.alternative_types]) + ')'
  def __repr__(self):
    return str(self)
  def __eq__(self, other):
    return isinstance(other, TupleType) \
      and all([t1 == t2 for t1,t2 in zip(self.alternative_types,
                                         other.alternative_types)])

@dataclass(eq=True, frozen=True)
class FunctionType(Type):
  type_params: tuple[str]
  param_types: tuple[tuple[str,Type]]
  return_type: Type
  requirements: list[AST]
  __match_args__ = ("type_params", "param_types", "return_type", "requirements")
  
  def __str__(self):
    return ('<' + ', '.join(self.type_params) + '>'
            if len(self.type_params) > 0\
            else '') \
           + '(' + ', '.join([k + ' ' + str(t) for k,t in self.param_types]) + ')' \
           + '->' + str(self.return_type) \
           + ' ' + ', '.join(str(req) for req in self.requirements)
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
  def __eq__(self, other):
    return isinstance(other, TypeVar) and self.ident == other.ident
              
  
@dataclass(eq=True, frozen=True)
class TypeApplication(Type):
  typeop: Type
  args: tuple[Type]
  __match_args__ = ("typeop", "args")

  def __str__(self):
      return str(self.typeop) + \
          "(" + ", ".join([str(arg) for arg in self.args]) + ")"

  def __repr__(self):
      return str(self)

@dataclass(eq=True, frozen=True)
class TypeOp(Type):
  params: list[str]
  type: Type
  __match_args__ = ("params", "type")


    
def unfold(ty: Type) -> Type:
  if isinstance(ty, RecursiveType):
    ret = substitute({ty.name: ty}, ty.type)
    return ret
  else:
    return ty

def require_consistent(ty1 : Type, ty2 : Type, msg: str, location: Meta):
  if not consistent(ty1, ty2):
    error(location, msg + ', ' + str(ty1) + ' inconsistent with ' + str(ty2))

def simplify(type: Type, env) -> Type:
  match type:
    case TypeVar(name):
      if name in env.keys():
        ret = env[name]
      else:
        error(type.location, "use of undefined type variable " + name)
    case TupleType(ts2):
      ret = TupleType(type.location,
                       tuple(simplify(elt_ty, env) for elt_ty in ts2))
    case PointerType(elt_ty):
      ret = PointerType(type.location, simplify(elt_ty, env))
    case ArrayType(elt_ty):
      ret = ArrayType(type.location, simplify(elt_ty, env))
    case RecursiveType(name, elt_ty):
      body_env = env.copy()
      body_env[name] = TypeVar(type.location, name)
      ret = RecursiveType(type.location, name, simplify(elt_ty, body_env))
    case FunctionType(ty_params, param_tys, ret_ty, requirements):
      body_env = env.copy()
      for k,t in ty_params:
        body_env[t] = TypeVar(type.location, t)
      ret = FunctionType(type.location,
                         ty_params,
                         tuple((k, simplify(ty, body_env)) \
                               for k,ty in param_tys),
                         simplify(ret_ty, body_env),
                         requirements) # TODO: simplify requirements
    case IntType():
      ret = type
    case RationalType():
      ret = type
    case BoolType():
      ret = type
    case AnyType():
      ret = type
    case VoidType():
      ret = type
    case RecordType(alts):
      ret = RecordType(type.location,
                        tuple((x, simplify(t, env)) for x,t in alts))
    case VariantType(alts):
      ret = VariantType(type.location,
                        tuple((x, simplify(t, env)) for x,t in alts))
    case TypeApplication(tyop, args):
      type_op = simplify(tyop, env)
      match type_op:
        case TypeOp(params, body):
          subst = {x:t for x,t in zip(params,
                                      [simplify(arg, env) for arg in args])}
          return simplify(substitute(subst, body), env)
        case _:
          error(type.location, "in simplify, expected type operator, not "
                + str(type_op))
      
    case _:
      error(type.location, "in simplify, unrecognized type " + str(type))
  return ret
      
def substitute(subst: dict[str, Type], ty2: Type) -> Type:
  match ty2:
    case TypeVar(name):
      if name in subst.keys():
        return subst[name]
      else:
        return ty2
    case TupleType(ts2):
      return TupleType(ty2.location,
                       tuple(substitute(subst, elt_ty) for elt_ty in ts2))
    case RecordType(alts):
      return RecordType(ty2.location,
                         tuple((x, substitute(subst, t)) for x,t in alts))
    case VariantType(alts):
      return VariantType(ty2.location,
                         tuple((x, substitute(subst, t)) for x,t in alts))
    case PointerType(elt_ty):
      return PointerType(ty2.location, substitute(subst, elt_ty))
    case ArrayType(elt_ty):
      return ArrayType(ty2.location, substitute(subst, elt_ty))
    case RecursiveType(name, ty):
      subst2 = subst.copy()
      subst2[name] = TypeVar(ty2.location, name)
      return RecursiveType(ty2.location, name, substitute(subst2, ty))
    case FunctionType(type_params, param_types, return_type):
      subst2 = subst.copy()
      for t in type_params:
        subst2[t] = TypeVar(ty2.location, t)
      params = tuple((k, substitute(subst2, pt)) for (k,pt) in param_types)
      ret = substitute(subst2, return_type)
      return FunctionType(ty2.location, type_params, params, ret,
                          tuple()) # TODO: handle requirements
    case IntType():
      return ty2
    case BoolType():
      return ty2
    case VoidType():
      return ty2
    case AnyType():
      return ty2
    case _:
      error(ty2.location, 'in substitute, unrecognized type ' + str(ty2))

def consistent(ty1: Type, ty2: Type, assumed_consistent=set()) -> bool:
  if (ty1,ty2) in assumed_consistent:
    return True
  match (ty1,ty2):
    case (AnyType(), _):
      result = True
    case (_, AnyType()):
      result = True
    case (RecursiveType(X, t1), _):
      assm = assumed_consistent | set([(ty1,ty2)])
      return consistent(unfold(ty1), ty2, assm)
    case (_, RecursiveType(X, t2)):
      assm = assumed_consistent | set([(ty1,ty2)])
      return consistent(ty1, unfold(ty2), assm)
    case (ArrayType(t1), ArrayType(t2)):
      result = consistent(t1, t2, assumed_consistent)
    case (PointerType(t1), PointerType(t2)):
      result = consistent(t1, t2, assumed_consistent)
    case (TupleType(ts1), TupleType(ts2)):
      result = all([consistent(t1, t2, assumed_consistent) \
                    for t1,t2 in zip(ts1, ts2)])
    case (VariantType(ts1), VariantType(ts2)):
      result = all([x1 == x2 and consistent(t1, t2, assumed_consistent) \
                    for (x1,t1),(x2,t2) in zip(ts1, ts2)])
    case (FunctionType(tp1, ps1, rt1), FunctionType(tp2, ps2, rt2)):
      # TODO: deal with type parameters
      result = all([consistent(t1, t2, assumed_consistent) \
                    for (k1,t1), (k2,t2) in zip(ps1, ps2)]) \
        and consistent(rt1,rt2, assumed_consistent)
    case (FutureType(t1), FutureType(t2)):
      result = consistent(t1, t2, assumed_consistent)
    case (IntType(), IntType()):
      result = True
    case (RationalType(), RationalType()):
      result = True
    case (IntType(), RationalType()):
      result = True
    case (RationalType(), IntType()):
      result = True
    case (BoolType(), BoolType()):
      result = True
    case (TypeVar(x), TypeVar(y)):
      result = x == y
    case _:
      result = False
  return result    

def join(ty1: Type, ty2: Type) -> Type:
  match (ty1,ty2):
    case (None, _):
      return ty2
    case (_, None):
      return ty1
    case (AnyType, _):
      return ty1
    case (_, AnyType):
      return ty2
    case (ArrayType(t1), ArrayType(t2)):
      return ArrayType(ty1.location, join(t1, t2))
    case (PointerType(t1), PointerType(t2)):
      return PointerType(join(t1, t2))
    case (TupleType(ts1), TupleType(ts2)):
      return TupleType(tuple(join(t1, t2) for t1,t2 in zip(ts1, ts2)))
    case (FunctionType(tp1, ps1, rt1), FunctionType(tp2, ps2, rt2)):
      return FunctionType(tp1,
                          # TODO join the k's
                          tuple((k1,join(t1, t2)) \
                                for (k1,t1), (k2,t2) in zip(ps1, ps2)),
                          join(rt1,rt2))
    case (FutureType(t1), FutureType(t2)):
      return FutureType(join(t1, t2))
    case (_, _):
      return ty1

def match_types(vars: tuple[str],
                pat_ty: Type,
                match_ty: Type,
                matches: dict[str,Type],
                assumed_consistent):
  if tracing_on():
    print('match\t' + str(pat_ty) + '\nwith\t' + str(match_ty)
          + '\nassuming\t' + str(assumed_consistent)
          + '\nmatches:\t' + str(matches))
  if (pat_ty, match_ty) in assumed_consistent:
    return True
  match (pat_ty, match_ty):
    case (AnyType(), _):
      return True
    case (_, AnyType()):
      return True
    case (TypeVar(name), _):
      if isinstance(match_ty, TypeVar) and name == match_ty.ident:
        return True
      elif name in matches.keys():
        return match_types(vars, matches[name], match_ty, matches,
                           assumed_consistent)
      elif name in vars:
        matches[name] = match_ty
        return True
      else:
        return False
    case (TupleType(pat_ts), TupleType(match_ts)):
      return all([match_types(vars, pt, mt, matches, assumed_consistent) \
                  for (pt,mt) in zip(pat_ts, match_ts)])
    case (VariantType(ts1), VariantType(ts2)):
      return all([x1 == x2 and match_types(vars, t1, t2, matches, \
                                           assumed_consistent) \
                  for (x1,t1),(x2,t2) in zip(ts1, ts2)])
    case (PointerType(pt), PointerType(mt)):
      return match_types(vars, pt, mt, matches, assumed_consistent)
    case (ArrayType(pt), ArrayType(mt)):
      return match_types(vars, pt, mt, matches, assumed_consistent)
    case (RecursiveType(X, t1), _):
      assm = assumed_consistent | set([(pat_ty,match_ty)])
      return match_types(vars, unfold(pat_ty), match_ty, matches, assm)
    case (_, RecursiveType(X, t2)):
      assm = assumed_consistent | set([(pat_ty,match_ty)])
      return match_types(vars, pat_ty, unfold(match_ty), matches, assm)
    case (FunctionType(tps1, pts1, rt1),
          FunctionType(tps2, pts2, rt2)):
      # TODO: handle type parameters
      return all([match_types(vars, pt1, pt2, matches, assumed_consistent) \
                  for ((k1,pt1), (k2,pt2)) in zip(pts1, pts2)]) \
             and match_types(vars, rt1, rt2, matches, assumed_consistent)
    case (IntType(), IntType()):
      return True
    case (RationalType(), RationalType()):
      return True
    case (BoolType(), BoolType()):
      return True
    case (VoidType(), VoidType()):
      return True
    case _:
      return False

@dataclass(frozen=True)
class StaticState:
  pass

# The variable is readable and globally immutable.
# A proper fraction is less-than 1 and greater than 0.
@dataclass(frozen=True)
class ProperFraction(StaticState):
  def __str__(self):
    return "1/N"
  def __repr__(self):
    return str(self)

# The variable is readable and writable.
@dataclass(frozen=True)
class FullFraction(StaticState):
  def __str__(self):
    return "1/1"
  def __repr__(self):
    return str(self)

# The variable is temporarily unusable.
@dataclass(frozen=True)
class EmptyFraction(StaticState):
  def __str__(self):
    return "0/1"
  def __repr__(self):
    return str(self)
  
# The variable has been consumed.
@dataclass(frozen=True)
class Dead(StaticState):
  def __str__(self):
    return "dead"
  def __repr__(self):
    return str(self)

def static_readable(frac):
    return isinstance(frac, ProperFraction) \
      or isinstance(frac, FullFraction)
  
@dataclass
class StaticInfo:
  def copy(self):
    raise Exception('unimplemented')

@dataclass
class StaticVarInfo(StaticInfo):
  type : Type
  translation : Exp = None
  state : StaticState = None
  param : Any = None # Param type
  
  def copy(self):
    return StaticVarInfo(self.type, self.translation,
                         self.state, self.param)
