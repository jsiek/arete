from abstract_syntax import *
from utilities import *

# TODO: need different type checking rules for ObserveCtx

def simplify(type: Type, env) -> Type:
  if tracing_on():
    print('trying to simplify ' + str(type))
  match type:
    case TypeVar(name):
      ret = env[name]
    case TupleType(ts2):
      ret = TupleType(type.location,
                       tuple(simplify(elt_ty, env) for elt_ty in ts2))
    case PointerType(elt_ty):
      ret = PointerType(type.location, simplify(elt_ty, env))
    case RecursiveType(name, elt_ty):
      body_env = env.copy()
      body_env[name] = TypeVar(type.location, name)
      ret = RecursiveType(type.location, name, simplify(elt_ty, body_env))
    case FunctionType(param_tys, ret_ty):
      ret = FunctionType(type.location,
                          [simplify(ty, env) for ty in param_tys],
                          simplify(ret_ty, env))
    case IntType():
      ret = type
    case BoolType():
      ret = type
    case AnyType():
      ret = type
    case VoidType():
      ret = type
    case _:
      error(type.location, "in simplify, unrecognized type " + str(type))
  if tracing_on():
    print('simplify ' + str(type) + ' to ' + str(ret))
  return ret
      
def substitute(var: str, ty1: Type, ty2: Type) -> Type:
  match ty2:
    case TypeVar(name):
      if var == name:
        return ty1
      else:
        return ty2
    case TupleType(ts2):
      return TupleType(ty2.location,
                       tuple(substitute(var, ty1, elt_ty) for elt_ty in ts2))
    case PointerType(elt_ty):
      return PointerType(ty2.location, substitute(var, ty1, elt_ty))
    case IntType():
      return ty2
    case BoolType():
      return ty2
    case _:
      error(ty1.location, 'in substitute, unrecognized type ' + str(ty2))

def unfold(ty):
  if isinstance(ty, RecursiveType):
    ret = substitute(ty.name, ty, ty.type)
    if tracing_on():
      print('unfolding ' + str(ty) + ' to ' + str(ret))
    return ret
  else:
    return ty

def consistent(ty1, ty2, assumed_consistent=set()):
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
    case (FunctionType(ps1, rt1), FunctionType(ps2, rt2)):
      result = all([consistent(t1, t2, assumed_consistent) \
                    for t1, t2 in zip(ps1, ps2)]) \
        and consistent(rt1,rt2, assumed_consistent)
    case (FutureType(t1), FutureType(t2)):
      result = consistent(t1, t2, assumed_consistent)
    case (IntType(), IntType()):
      result = True
    case (RationalType(), RationalType()):
      result = True
    case (BoolType(), BoolType()):
      result = True
    case _:
      result = False
  if tracing_on():
    print("consistent(" + str(ty1) + ',' + str(ty2) + ") = " + str(result))
  return result    

def join(ty1, ty2):
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
    case (FunctionType(ps1, rt1), FunctionType(ps2, rt2)):
      return FunctionType([join(t1, t2) for t1, t2 in zip(ps1, ps2)],
                          join(rt1,rt2))
    case (FutureType(t1), FutureType(t2)):
      return FutureType(join(t1, t2))
    case (_, _):
      return ty1
    
def type_check_init(init, env):
    match init:
      case Initializer(loc, percent, arg):
        if percent == 'default':
          percent_type = RationalType(init.location)
        else:
          percent_type = type_check_exp(percent, env)
        percent_type = unfold(percent_type)
        if isinstance(percent_type, RationalType) \
           or isinstance(percent_type, IntType):
          arg_type = type_check_exp(arg, env)
          return arg_type
        elif isinstance(percent_type, AnyType):
          return AnyType(loc)
        else:
          error(init.location, 'in initializer, expected percentage '
                + 'not ' + str(percent_type))
      case _:
        error(init.location, 'in type_check_init, expected an initializer, not '
              + repr(init))

def type_check_prim(location, op, arg_types):
    arg_types = [unfold(arg_ty) for arg_ty in arg_types]
    match op:
      case 'copy':
        return arg_types[0]
      case 'len':
        assert len(arg_types) == 1
        assert isinstance(arg_types[0], ArrayType) \
          or isinstance(arg_types[0], TupleType) \
          or isinstance(arg_types[0], AnyType)
        return IntType(location)
      case 'equal':
        assert len(arg_types) == 2
        if not consistent(arg_types[0], arg_types[1]):
          error(location, 'equal operator, '
                + str(arg_types[0]) + ' not consistent with '
                + str(arg_types[1]))
        return BoolType(location)
      case 'not_equal':
        assert len(arg_types) == 2
        assert consistent(arg_types[0], arg_types[1])
        return BoolType(location)
      case 'add':
        assert len(arg_types) == 2
        assert consistent(arg_types[0], IntType(location))
        assert consistent(arg_types[1], IntType(location))
        return IntType(location)
      case 'sub':
        assert len(arg_types) == 2
        assert consistent(arg_types[0], IntType(location))
        assert consistent(arg_types[1], IntType(location))
        return IntType(location)
      case 'mul':
        assert len(arg_types) == 2
        assert consistent(arg_types[0], IntType(location))
        assert consistent(arg_types[1], IntType(location))
        return IntType(location)
      case 'div':
        assert len(arg_types) == 2
        assert consistent(arg_types[0], IntType(location))
        assert consistent(arg_types[1], IntType(location))
        return RationalType(location)
      case 'int_div':
        assert len(arg_types) == 2
        assert consistent(arg_types[0], IntType(location))
        assert consistent(arg_types[1], IntType(location))
        return IntType(location)
      case 'neg':
        assert len(arg_types) == 1
        assert consistent(arg_types[0], IntType(location))
        return IntType(location)
      case 'and':
        assert len(arg_types) == 2
        assert consistent(arg_types[0], BoolType(location))
        assert consistent(arg_types[1], BoolType(location))
        return BoolType(location)
      case 'or':
        assert len(arg_types) == 2
        assert consistent(arg_types[0], BoolType(location))
        assert consistent(arg_types[1], BoolType(location))
        return BoolType(location)
      case 'not':
        assert len(arg_types) == 1
        assert consistent(arg_types[0], BoolType(location))
        return BoolType(location)
      case 'null':
        assert len(arg_types) == 0
        return PointerType(location, AnyType(location))
      case 'is_null':
        assert len(arg_types) == 1
        assert isinstance(arg_types[0], PointerType) \
          or isinstance(arg_types[0], AnyType)
        return BoolType(location)
      case 'split':
        assert len(arg_types) == 1
        assert isinstance(arg_types[0], PointerType) \
          or isinstance(arg_types[0], AnyType)
        return TupleType(location, (arg_types[0], arg_types[0]))
      case 'join':
        assert len(arg_types) == 2
        # assert isinstance(arg_types[0], PointerType) \
        #   or isinstance(arg_types[0], ArrayType) \
        #   or isinstance(arg_types[0], AnyType)
        # assert isinstance(arg_types[1], PointerType) \
        #   or isinstance(arg_types[1], ArrayType) \
        #   or isinstance(arg_types[1], AnyType)
        assert consistent(arg_types[0], arg_types[1])
        return join(arg_types[0], arg_types[1])
      case 'permission':
        assert len(arg_types) == 1
        # assert isinstance(arg_types[0], PointerType) \
        #   or isinstance(arg_types[0], ArrayType) \
        #   or isinstance(arg_types[0], AnyType)
        return RationalType(location)
      case 'upgrade':
        assert len(arg_types) == 1
        # assert isinstance(arg_types[0], PointerType) \
        #   or isinstance(arg_types[0], ArrayType) \
        #   or isinstance(arg_types[0], AnyType)
        return BoolType(location)
      case cmp if cmp in compare_ops.keys():
        assert len(arg_types) == 2
        assert consistent(arg_types[0], IntType(location))
        assert consistent(arg_types[1], IntType(location))
        return BoolType(location)
      case _:
        error(location, 'in type_check_prim, unknown primitive operator ' + op)

  
def type_check_exp(e, env):
    match e:
      case Var(x):
        if x not in env:
            error(e.location, 'use of undefined variable ' + x)
        return env[x]
      case Int(n):
        return IntType(e.location)
      case Frac(f):
        return RationalType(e.location)
      case Bool(b):
        return BoolType(e.location)
      case Prim(op, args):
        arg_types = [type_check_exp(arg, env) for arg in args]
        return type_check_prim(e.location, op, arg_types)
      case Member(arg, field):
        mod_type = type_check_exp(arg, env)
        mod_type = unfold(mod_type)
        if not isinstance(mod_type, ModuleType):
            error(e.location, "expected a module, not " + str(mod_type))
        if not field in mod_type.member_types.keys():
            error(e.location, "module " + str(arg) + " does not contain "
                  + field)
        return mod_type.member_types[field]
      case New(init):
        init_type = type_check_init(init, env)
        return PointerType(e.location, init_type)
      case Array(size, arg):
        size_type = type_check_exp(size, env)
        arg_type = type_check_exp(arg, env)
        if not (isinstance(size_type, IntType)
                or isinstance(size_type, AnyType)):
            error(e.location, "expected integer array size, not "
                  + str(size_type))
        return ArrayType(e.location, arg_type)
      case TupleExp(inits):
        init_types = tuple(type_check_init(init, env) for init in inits)
        return TupleType(e.location, init_types)
      case Lambda(params, ret_mode, body, name):
        body_env = env.copy()
        for p in params:
            body_env[p.ident] = p.type_annot
        ret_type = type_check_stmt(body, body_env)
        return FunctionType(e.location, [p.type_annot for p in params],
                            ret_type)
      case Call(fun, inits):
        fun_type = type_check_exp(fun, env)
        arg_types = [type_check_init(init, env) for init in inits]
        fun_type = unfold(fun_type)
        if isinstance(fun_type, FunctionType):
          for (param_ty, arg_ty) in zip(fun_type.param_types, arg_types):
              if not consistent(simplify(param_ty, env), arg_ty):
                  error(e.location, 'in call, '
                        + 'expected argument of type ' + str(param_ty)
                        + ' not ' + str(arg_ty))
          return simplify(fun_type.return_type, env)
        elif isinstance(fun_type, AnyType):
          return AnyType(e.location)
        else:
          error(e.location, "in call, expected a function, not "
                + str(fun_type))
      case Index(arg, index):
        arg_type = type_check_exp(arg, env)
        index_type = type_check_exp(index, env)
        arg_type = unfold(arg_type)
        if isinstance(arg_type, TupleType):
          if isinstance(index, Int):
            if 0 <= index.value and index.value < len(arg_type.member_types):
              return arg_type.member_types[index.value]
            else:
              error(e.location, 'index ' + str(index.value)
                    + ' out of bounds for pointer ' + str(arg_type))
          else:
            error(e.location, 'in subscript, expected an integer index, not '
                  + str(index))
        elif isinstance(arg_type, ArrayType):
          return arg_type.element_type
        elif isinstance(arg_type, AnyType):
          return AnyType(e.location)
        else:
          error(e.location, 'in subscript, expected tuple or array, not '
                + str(arg_type))
      case Deref(arg):
        arg_type = type_check_exp(arg, env)
        arg_type = unfold(arg_type)
        if isinstance(arg_type, PointerType):
          return arg_type.type
        # elif isinstance(arg_type, ArrayType):
        #   return arg_type.element_type
        elif isinstance(arg_type, AnyType):
          return AnyType(e.location)
        else:
          error(e.location, 'in deref, expected a pointer, not '
                + str(arg_type))
      case AddressOf(arg):
        arg_type = type_check_exp(arg, env)
        return arg_type # or pointer to arg_type? -Jeremy
      case IfExp(cond, thn, els):
        cond_type = type_check_exp(cond, env)
        thn_type = type_check_exp(thn, env)
        els_type = type_check_exp(els, env)
        if not (isinstance(cond_type, BoolType)
                or isinstance(cond_type, AnyType)):
          error(e.location, 'in conditional, expected a Boolean, not '
                + str(cond_type))
        if not consistent(thn_type, els_type):
          error(e.location, 'in conditional, branches must be consistent, not '
                + str(cond_type))
        return join(thn_type, els_type)
      case Let(var, init, body):
        init_type = type_check_init(init, env)
        body_env = env.copy()
        body_env[var.ident] = init_type
        body_type = type_check_exp(body, body_env)
        return body_type
      case FutureExp(arg):
        arg_type = type_check_exp(arg, env)
        return FutureType(e.location, arg_type)
      case Await(arg):
        arg_type = type_check_exp(arg, env)
        arg_type = unfold(arg_type)
        if isinstance(arg_type, FutureType):
          return arg_type.result_type
        elif isinstance(arg_type, AnyType):
          return AnyType(e.location)
        else:
          error(arg.location, 'in await, expected a future, not '
                + str(arg_type))
      case _:
        error(e.location, 'error in type_check_exp, unhandled: ' + repr(e)) 
    
def type_check_stmt(s, env):
    match s:
      case LetInit(var, init, body):
        init_type = type_check_init(init, env)
        type_annot = simplify(var.type_annot, env)
        if not consistent(init_type, type_annot):
          error(s.location, 'initializing type ' + str(init_type) + '\n'
                + ' is inconsistent with declared type ' + str(type_annot))
        body_env = env.copy()
        body_env[var.ident] = type_annot
        body_type = type_check_stmt(body, body_env)
        return body_type
      case Seq(first, rest):
        first_type = type_check_stmt(first, env)
        rest_type = type_check_stmt(rest, env)
        return join(first_type, rest_type) # ??
      case Return(arg):
        arg_type = type_check_exp(arg, env)
        return arg_type
      case Pass():
        return None
      case Write(lhs, rhs):
        lhs_type = type_check_exp(lhs, env)
        rhs_type = type_check_init(rhs, env)
        # TODO
        return None
      case Transfer(lhs, percent, rhs):
        # lhs_type = type_check_exp(lhs, env)
        percent_type = type_check_exp(percent, env)
        # rhs_type = type_check_exp(rhs, env)
        # TODO
        return None
      case Expr(arg):
        type_check_exp(arg, env)
        return None
      case Assert(arg):
        arg_type = type_check_exp(arg, env)
        # TODO
        return None
      case Delete(arg):
        arg_type = type_check_exp(arg, env)
        # TODO
        return None
      case IfStmt(cond, thn, els):
        cond_type = type_check_exp(cond, env)
        thn_type = type_check_stmt(thn, env)
        els_type = type_check_stmt(els, env)
        return join(thn_type, els_type)
      case While(cond, body):
        cond_type = type_check_exp(cond, env)
        body_type = type_check_stmt(body, env)
        return body_type
      case Block(body):
        return type_check_stmt(body, env)
      case _:
        error(s.location, 'error in type_check_stmt, unhandled: ' + repr(s)) 

def typeof_decl(decl, env):
  match decl:
    case Global(name, ty, rhs):
      ret = simplify(ty, env)
    case Function(name, params, ret_ty, ret_mode, body):
      ty = FunctionType(decl.location, [p.type_annot for p in params], ret_ty)
      ret = simplify(ty, env)
    case ModuleDecl(name, exports, body):
      member_types = {}
      for d in body:
        if not isinstance(d, Import):
          member_types[d.name] = typeof_decl(d, env)
      ret = ModuleType(decl.location, member_types)
    case _:
      error(decl.location, 'error in typeof_decl, unhandled: ' + str(decl))
  if tracing_on() and hasattr(decl, 'name'):
    print('typeof ' + decl.name + ' = ' + str(ret))
  return ret
    
def declare_decl(decl, env):
    match decl:
      case Import(module, imports):
        mod = type_check_exp(module, env)
        mod = unfold(mod)
        if isinstance(mod, ModuleType):
          for x in imports:
              if not x in mod.member_types.keys():
                error(decl.location, "in import, no " + x
                      + " in " + str(module))
              env[x] = mod.member_types[x]
        else:
          error(decl.location, "in import, expected a module, not " + str(mod))
      case TypeDecl(name, type):
        env[name] = simplify(type, env)
      case _:
        env[decl.name] = typeof_decl(decl, env)
    
def type_check_decl(decl, env):
  match decl:
    case Global(name, ty, rhs):
      rhs_type = type_check_exp(rhs, env)
      # TODO
    case Function(name, params, ret_ty, ret_mode, body):
      ret_ty = simplify(ret_ty, env)
      body_env = env.copy()
      for p in params:
          body_env[p.ident] = simplify(p.type_annot, env)
      body_type = type_check_stmt(body, body_env)
      if not consistent(body_type, ret_ty):
        error(decl.location, 'return type mismatch:\n' + str(ret_ty) + ' inconsistent with '
              + str(body_type))
      
    case ModuleDecl(name, exports, body):
      type_check_decls(body, env)

    case Import(module, imports):
      # TODO
      pass

    case TypeDecl(name, type):
      pass
      
    
def type_check_decls(decls, env):
    body_env = env.copy()
    for d in decls:
      declare_decl(d, body_env)
    for d in decls:
      type_check_decl(d, body_env)
        
    
