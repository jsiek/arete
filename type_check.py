from abstract_syntax import *
from utilities import *

# TODO: need different type checking rules for ObserveCtx

def require_consistent(ty1 : Type, ty2 : Type, msg: str, location: Meta):
  if not consistent(ty1, ty2):
    error(location, msg + ', ' + str(ty1) + ' inconsistent with ' + str(ty2))

def simplify(type: Type, env) -> Type:
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
    case FunctionType(ty_params, param_tys, ret_ty):
      body_env = env.copy()
      for t in ty_params:
        body_env[t] = TypeVar(type.location, t)
      ret = FunctionType(type.location,
                         ty_params,
                         tuple(simplify(ty, body_env) for ty in param_tys),
                         simplify(ret_ty, body_env))
    case IntType():
      ret = type
    case BoolType():
      ret = type
    case AnyType():
      ret = type
    case VoidType():
      ret = type
    case VariantType(alts):
      ret = VariantType(type.location,
                        tuple((x, simplify(t, env)) for x,t in alts))
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
      params = tuple(substitute(subst2, pt) for pt in param_types)
      ret = substitute(subst2, return_type)
      return FunctionType(ty2.location, type_params, params, ret)
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

def unfold(ty: Type) -> Type:
  if isinstance(ty, RecursiveType):
    ret = substitute({ty.name: ty}, ty.type)
    return ret
  else:
    return ty

def consistent(ty1: Type, ty2: Type, assumed_consistent=set()) -> Bool:
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
                    for t1, t2 in zip(ps1, ps2)]) \
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
                          tuple(join(t1, t2) for t1, t2 in zip(ps1, ps2)),
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
          + '\nin\t' + str(assumed_consistent))
  if (pat_ty, match_ty) in assumed_consistent:
    return True
  match (pat_ty, match_ty):
    case (AnyType(), _):
      return True
    case (_, AnyType()):
      return True
    case (TypeVar(name), _):
      if name in matches.keys():
        return match_types(vars, matches[name], match_ty, assumed_consistent)
      elif name in vars:
        matches[name] = match_ty
        return True
      else:
        match match_ty:
          case TypeVar(other_name):
            return name == other_name
          case _:
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
                  for (pt1, pt2) in zip(pts1, pts2)]) \
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
      error(pat_ty.location, 'in match_types, unrecognized types:\n'
            + str(pat_ty) + '\n' + str(match_ty))
    
def type_check_prim(location, op, arg_types):
    arg_types = [unfold(arg_ty) for arg_ty in arg_types]
    match op:
      case 'breakpoint':
        assert len(arg_types) == 0;
        return VoidType(location)
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
        require_consistent(arg_types[0], arg_types[1], 'in !=', location)
        return BoolType(location)
      case 'add':
        assert len(arg_types) == 2
        require_consistent(arg_types[0], IntType(location), 'in +', location)
        require_consistent(arg_types[1], IntType(location), 'in +', location)
        return IntType(location)
      case 'sub':
        assert len(arg_types) == 2
        require_consistent(arg_types[0], IntType(location), 'in -', location)
        require_consistent(arg_types[1], IntType(location), 'in -', location)
        return IntType(location)
      case 'mul':
        assert len(arg_types) == 2
        require_consistent(arg_types[0], IntType(location), 'in *', location)
        require_consistent(arg_types[1], IntType(location), 'in *', location)
        return IntType(location)
      case 'div':
        assert len(arg_types) == 2
        require_consistent(arg_types[0], IntType(location), 'in /', location)
        require_consistent(arg_types[1], IntType(location), 'in /', location)
        return RationalType(location)
      case 'int_div':
        assert len(arg_types) == 2
        require_consistent(arg_types[0], IntType(location), 'in //', location)
        require_consistent(arg_types[1], IntType(location), 'in //', location)
        return IntType(location)
      case 'neg':
        assert len(arg_types) == 1
        require_consistent(arg_types[0], IntType(location), 'in -', location)
        return IntType(location)
      case 'and':
        assert len(arg_types) == 2
        require_consistent(arg_types[0], BoolType(location), 'in and', location)
        require_consistent(arg_types[1], BoolType(location), 'in and', location)
        return BoolType(location)
      case 'or':
        assert len(arg_types) == 2
        require_consistent(arg_types[0], BoolType(location), 'in or', location)
        require_consistent(arg_types[1], BoolType(location), 'in or', location)
        return BoolType(location)
      case 'not':
        assert len(arg_types) == 1
        require_consistent(arg_types[0], BoolType(location), 'in not', location)
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
        require_consistent(arg_types[0], arg_types[1], 'in join', location)
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
        require_consistent(arg_types[0], IntType(location), 'in ' + cmp, location)
        require_consistent(arg_types[1], IntType(location), 'in ' + cmp, location)
        return BoolType(location)
      case _:
        error(location, 'in type_check_prim, unknown primitive operator ' + op)

  
def type_check_exp(e, env):
    match e:
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
      case PrimitiveCall(op, args):
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
      case Array(size, arg):
        size_type = type_check_exp(size, env)
        arg_type = type_check_exp(arg, env)
        if not (isinstance(size_type, IntType)
                or isinstance(size_type, AnyType)):
            error(e.location, "expected integer array size, not "
                  + str(size_type))
        return ArrayType(e.location, arg_type)
      case TupleExp(inits):
        init_types = tuple(type_check_exp(init, env) for init in inits)
        return TupleType(e.location, init_types)
      case TagVariant(tag, arg, ty_annot):
        ty = simplify(ty_annot, env)
        if not (isinstance(ty, VariantType) or isinstance(ty, AnyType)):
          error(e.location, 'expected variant type in tagging, not '
                + str(ty_annot))
        arg_ty = type_check_exp(arg, env)
        if isinstance(ty, VariantType):
          found = False
          for (alt_tag, alt_ty) in ty.alternative_types:
            if tag == alt_tag:
              if not consistent(arg_ty, alt_ty):
                error(e.location, 'expected ' + str(alt_ty) + '\nnot ' 
                      + str(arg_ty))
              found = True
          if not found:
            error(e.location, 'no tag ' + tag + ' in ' + str(ty_annot))
        return ty
      case Lambda(params, ret_mode, body, name):
        body_env = env.copy()
        for p in params:
            body_env[p.ident] = p.type_annot
        ret_type = type_check_statement(body, body_env)
        return FunctionType(e.location,
                            tuple(),
                            tuple(p.type_annot for p in params),
                            ret_type)
      case Call(fun, inits):
        fun_type = type_check_exp(fun, env)
        arg_types = [type_check_exp(init, env) for init in inits]
        fun_type = unfold(fun_type)
        if tracing_on():
          print('call to function of type ' + str(fun_type))
        if isinstance(fun_type, FunctionType):
          fun_env = env.copy()
          for t in fun_type.type_params:
            fun_env[t] = TypeVar(e.location, t)
          # perform type argument deduction
          matches = {}
          for (param_ty, arg_ty) in zip(fun_type.param_types, arg_types):
              pt = simplify(param_ty, fun_env)
              if not match_types(fun_type.type_params, pt, arg_ty, matches,
                                 set()):
                  error(e.location, 'in call, '
                        + 'expected type ' + str(param_ty)
                        + ' not ' + str(arg_ty))
          if tracing_on():
            print('deduced: ' + str(matches))
          rt = simplify(fun_type.return_type, fun_env)
          return substitute(matches, rt)
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
        return PointerType(e.location, arg_type)
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
      case BindingExp(param, rhs, body):
        rhs_type = type_check_exp(rhs, env)
        type_annot = simplify(param.type_annot, env)
        if not consistent(rhs_type, type_annot):
          error(e.location, 'type of initializer ' + str(rhs_type) + '\n'
                + ' is inconsistent with declared type ' + str(type_annot))
        body_env = env.copy()
        body_env[param.ident] = rhs_type
        body_type = type_check_exp(body, body_env)
      case FutureExp(arg):
        arg_type = type_check_exp(arg, env)
        return FutureType(e.location, arg_type)
      case Wait(arg):
        arg_type = type_check_exp(arg, env)
        arg_type = unfold(arg_type)
        if isinstance(arg_type, FutureType):
          return arg_type.result_type
        elif isinstance(arg_type, AnyType):
          return AnyType(e.location)
        else:
          error(arg.location, 'in wait, expected a future, not '
                + str(arg_type))
      case _:
        error(e.location, 'error in type_check_exp, unhandled: ' + repr(e)) 
    
def type_check_statement(s, env):
    match s:
      case BindingStmt(param, rhs, body):
        rhs_type = type_check_exp(rhs, env)
        type_annot = simplify(param.type_annot, env)
        if not consistent(rhs_type, type_annot):
          error(s.location, 'type of initializer ' + str(rhs_type) + '\n'
                + ' is inconsistent with declared type ' + str(type_annot))
        body_env = env.copy()
        body_env[param.ident] = type_annot
        body_type = type_check_statement(body, body_env)
        return body_type
      case Seq(first, rest):
        first_type = type_check_statement(first, env)
        rest_type = type_check_statement(rest, env)
        return join(first_type, rest_type) # ??
      case Return(arg):
        arg_type = type_check_exp(arg, env)
        return arg_type
      case Pass():
        return None
      case Write(lhs, rhs):
        lhs_type = type_check_exp(lhs, env)
        rhs_type = type_check_exp(rhs, env)
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
        thn_type = type_check_statement(thn, env)
        els_type = type_check_statement(els, env)
        return join(thn_type, els_type)
      case While(cond, body):
        cond_type = type_check_exp(cond, env)
        body_type = type_check_statement(body, env)
        return body_type
      case Block(body):
        return type_check_statement(body, env)
      case Match(cond, cases):
        cond_ty = type_check_exp(cond, env)
        if not (isinstance(cond_ty, VariantType) \
                or isinstance(cond_ty, AnyType)):
          error(e.location, 'expected variant type in match, not '
                + str(cond_ty))
        return_type = None
        for (tag, x, body) in cases:
          # tag in the variant type?
          if isinstance(cond_ty, VariantType):
            found = False
            for (alt_tag,alt_ty) in cond_ty.alternative_types:
              if tag == alt_tag:
                body_env = env.copy()
                body_env[x] = alt_ty
                retty = type_check_statement(body, body_env)
                if return_type is None:
                  return_type = retty
                elif not retty is None:
                  return_type = join(retty, return_type)
                found = True
            if found == False:
              error(s.location, tag + ' is not a tag in ' + str(cond_ty))
        return return_type
        # TODO: check for completeness of the cases wrt the cond_ty
      case _:
        error(s.location, 'error in type_check_statement, unhandled: '
              + repr(s))

def typeof_decl(decl, env):
  match decl:
    case _:
      error(decl.location, 'error in typeof_decl, unhandled: ' + str(decl))
  return ret

# This function is responsible for collecting up the declared types of
# the declarations and adding them to the environment and to the
# output (for members of a module).
def declare_decl(decl, env, output):
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
            output[x] = env[x]
      else:
        error(decl.location, "in import, expected a module, not " + str(mod))
    case TypeAlias(name, type):
      env[name] = simplify(type, env)
    case Global(name, ty, rhs):
      env[name] = simplify(ty, env)
      output[name] = env[name]
    case Function(name, ty_params, params, ret_ty, ret_mode, body):
      ty = FunctionType(decl.location,
                        ty_params,
                        tuple(p.type_annot for p in params),
                        ret_ty)
      env[name] = simplify(ty, env)
      output[name] = env[name]
    case ModuleDef(name, exports, body):
      member_types = {}
      for d in body:
        declare_decl(d, env, member_types)
      env[name] = ModuleType(decl.location, member_types)
      output[name] = env[name]

# This function is responsible for type checking the internals of the
# definitions, such as the body of a function or the initializing
# expression of a global variable.
def type_check_decl(decl, env):
  match decl:
    case Global(name, ty, rhs):
      rhs_type = type_check_exp(rhs, env)
      type_annot = simplify(ty, env)
      if not consistent(rhs_type, type_annot):
        error(decl.location, 'type of initializer ' + str(rhs_type) + '\n'
              + ' is inconsistent with declared type ' + str(type_annot))
    case Function(name, ty_params, params, ret_ty, ret_mode, body):
      body_env = env.copy()
      for t in ty_params:
        body_env[t] = TypeVar(decl.location, t)
      ret_ty = simplify(ret_ty, body_env)
      for p in params:
          body_env[p.ident] = simplify(p.type_annot, body_env)
      body_type = type_check_statement(body, body_env)
      if not consistent(body_type, ret_ty):
        error(decl.location, 'return type mismatch:\n' + str(ret_ty)
              + ' inconsistent with ' + str(body_type))
    case ModuleDef(name, exports, body):
      body_env = env.copy()
      members = {}
      for d in body:
        declare_decl(d, body_env, members)
      for d in body:
        type_check_decl(d, body_env)
    case Import(module, imports):
      # the checking was done in declare_decl 
      pass
    case TypeAlias(name, type):
      # the work was done in declare_decl 
      pass
    
def type_check_program(decls):
    env = {}
    for d in decls:
      declare_decl(d, env, env)
    for d in decls:
      type_check_decl(d,  env)
        
    
