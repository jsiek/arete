#
# This file defines the language features related to functions in Arete,
# which includes
# * function values (closures),
# * module-level function definitions,
# * function calls,
# * return statements, and
# * lambda expressions.
#

from dataclasses import dataclass
from variables_and_binding import Param, clear_borrowed_vars, get_borrowed_vars
from ast_base import *
from ast_types import *
from values import Result, Pointer
from utilities import *
from abstract_syntax import make_cast


# ========================================================================
@dataclass
class Closure(Value):
    name: str
    params: list[Any]
    return_mode: str  # 'value' or 'address'
    requirements: list[AST]
    body: Stmt
    env: dict[str, Pointer]
    __match_args__ = ("name", "params", "return_mode", "requirements",
                      "body", "env")

    def duplicate(self, percentage, loc):
        if tracing_on():
            print('duplicating closure ' + str(self) + ' at ' + str(percentage))
        env_copy = {x: v.duplicate(percentage, loc) \
                    for x, v in self.env.items()}
        return Closure(self.name, self.params, self.return_mode,
                       self.requirements,
                       self.body, env_copy)

    def kill(self, mem, location, progress=set()):
        if tracing_on():
            print('kill closure ' + str(self))
        for x, ptr in self.env.items():
            ptr.kill(mem, location, progress)

    def clear(self, mem, location, progress=set()):
        for x, ptr in self.env.items():
            ptr.kill(mem, location, progress)

    def __str__(self):
        if verbose():
            return '<' + self.name + '>' + '(' \
                   + ', '.join([str(ptr) for x, ptr in self.env.items()]) + ')'
        else:
            return '<' + self.name + '>'

    def __repr__(self):
        return str(self)

    def node_name(self):
        return str(self.name)

    def node_label(self):
        return 'fun ' + str(self.name) + '(' \
               + ', '.join([ptr.node_label() for x, ptr in self.env.items()]) + ')'


# ========================================================================
@dataclass
class Function(Decl):
    name: str
    type_params: list[str]
    params: list[Param]
    return_type: Type
    return_mode: str  # 'value' or 'address'
    requirements: list[AST]
    body: Exp
    __match_args__ = ("name", "type_params", "params", "return_type",
                      "return_mode", "requirements", "body")

    def __str__(self):
        return "fun " + self.name \
               + ("<" + ", ".join(self.type_params) + ">"
                      if len(self.type_params) > 0
                      else "") \
               + "(" + ", ".join([str(p) for p in self.params]) + ")" \
               + " -> " + str(self.return_type) + " " \
               + ", ".join([str(req) for req in self.requirements]) \
               + " " + str(self.body)

    def __repr__(self):
        return str(self)

    def free_vars(self):
        req_vars = set()
        for req in self.requirements:
            req_vars |= {req.name} | req.iface.members.keys()
            for extend_req in req.iface.extends:
                req_vars |= {extend_req.name}

        params = set([p.ident for p in self.params])
        fvars = body.free_vars() - params - req_vars
        if tracing_on():
            print('function ' + self.name + ' free variables: ' + str(fvars)
                  + '\nrequirements: ' + str(req_mem_vars))
        return fvars

    def const_eval(self, env):
        body_env = env.copy()
        for t in self.type_params:
            body_env[t] = TypeVar(self.location, t)
        new_params = [p.with_type(simplify(p.type_annot, body_env)) \
                      for p in self.params]
        new_return_ty = simplify(self.return_type, body_env)
        # TODO const_eval the self.requirements
        for p in new_params:
            if p.ident in body_env.keys():
                del body_env[p.ident]
        new_body = self.body.const_eval(body_env)
        return [Function(self.location, self.name, self.type_params,
                         new_params, new_return_ty,
                         self.return_mode, self.requirements, new_body)]

    def declare_type(self, env):
        ty = FunctionType(self.location,
                          self.type_params,
                          tuple((p.kind, p.type_annot) for p in self.params),
                          self.return_type,
                          tuple(self.requirements))
        return {self.name: StaticVarInfo(ty, None, ProperFraction())}

    def type_check(self, env):
        if tracing_on():
            print('type checking function ' + str(self))
            print(env)
        body_env = copy_type_env(env)
        for t in self.type_params:
            tyvar = TypeVar(self.location, t)
            body_env[t] = StaticVarInfo(tyvar, tyvar)  # ???
        new_return_type = self.return_type
        new_params = [p for p in self.params]

        # Bind parameters to their types
        for p in new_params:
            p.bind_type(body_env)

        # Bring the impls and their members into scope.
        # Add parameters for the witnesses.
        for req in self.requirements:
            (new_param, req_env) = req.declare(body_env)
            body_env = merge_type_env(body_env, req_env)
            new_params.append(new_param)

        # type check the body of the function
        new_body = self.body.type_check(body_env, new_return_type)
        new_fun = Function(self.location, self.name, self.type_params,
                           new_params, new_return_type,
                           self.return_mode, [], new_body)
        if tracing_on():
            print('finished type checking function\n' + str(new_fun))
        return [new_fun]

    def step(self, runner, machine):
        if runner.state == 0:
            lam = Lambda(self.location, self.params, [], self.return_mode,
                         self.requirements, self.body, self.name)
            machine.schedule(lam, runner.env)
        else:
            machine.memory.unchecked_write(runner.env[self.name],
                                           runner.results[0].value,
                                           self.location)
            machine.finish_definition(self.location)


# ========================================================================
@dataclass
class Call(Exp):
    fun: Exp
    args: list[Exp]

    __match_args__ = ("fun", "args")

    def __str__(self):
        return str(self.fun) \
               + "(" + ", ".join([str(arg) for arg in self.args]) + ")"

    def __repr__(self):
        return str(self)

    def free_vars(self):
        return self.fun.free_vars() \
               | set().union(*[arg.free_vars() for arg in self.args])

    def const_eval(self, env):
        new_fun = self.fun.const_eval(env)
        new_args = [arg.const_eval(env) for arg in self.args]
        return Call(self.location, new_fun, new_args)

    def type_argument_deduction(self, type_params, param_types, arg_types):
        deduced_types = {}
        for ((kind, param_ty), arg_ty) in zip(param_types, arg_types):
            if not match_types(type_params, param_ty, arg_ty,
                               deduced_types, set()):
                error(self.location, 'in call, '
                      + str(self) + '\n'
                      + 'argument type:\n\t' + str(arg_ty)
                      + '\ndoes not match parameter type:\n\t' + str(param_ty))
        return deduced_types

    def type_check(self, env, ctx):
        fun_type, new_fun = self.fun.type_check(env, 'none')
        # types of the arguments
        arg_types = []
        # translated arguments
        new_args = []

        if isinstance(fun_type, FunctionType):
            param_kinds = [k for k, t in fun_type.param_types]
        else:
            param_kinds = ['let' for e in self.args]

        # type check (and translate) the arguments
        clear_borrowed_vars()
        for arg, kind in zip(self.args, param_kinds):
            arg_type, new_arg = arg.type_check(env, kind)
            arg_types.append(arg_type)
            new_args.append(new_arg)

        # restore info of variables that we borrowed from
        for var, old_info in get_borrowed_vars().items():
            env[var] = old_info

        fun_type = unfold(fun_type)
        if isinstance(fun_type, FunctionType):
            if len(fun_type.param_types) != len(arg_types):
                static_error(self.location, 'incorrect number of arguments: '
                             + str(len(arg_types))
                             + '\nexpected: ' + str(len(fun_type.param_types)))

            param_types = fun_type.param_types
            rt = fun_type.return_type

            deduced_types = self.type_argument_deduction(fun_type.type_params,
                                                         param_types, arg_types)
            if tracing_on():
                print('deduced: ' + str(deduced_types))

            for req in fun_type.requirements:
                wit_exp = req.satisfy_impl(deduced_types, env, self.location)
                new_args.append(wit_exp)

            inst_param_types = [substitute(deduced_types, pt)
                                for (kind,pt) in param_types]
            cast_args = []
            for arg, arg_type, param_type in zip(new_args, arg_types,
                                                 inst_param_types):
                cast_args.append(make_cast(arg, arg_type, param_type))

            ret = substitute(deduced_types, rt)
            if tracing_on():
                print('finished type checking: ' + str(self))
                print('type: ' + str(ret))
            return ret, Call(self.location, new_fun, cast_args)
        elif isinstance(fun_type, AnyType):
            cast_args = []
            for arg, arg_type in zip(new_arg, arg_types):
                cast_args.append(make_cast(arg, arg_type, AnyType(self.location)))
            return AnyType(self.location), \
                   Call(self.location, new_fun, cast_args)
        else:
            static_error(self.location, "in call, expected a function, not "
                         + str(fun_type))

    def set_closure(self, runner, machine):
        if runner.clos is None:
            runner.clos = runner.results[0].value
            if not isinstance(runner.clos, Closure):
                error(self.location, 'expected function in call, not '
                      + str(runner.clos))

    def step(self, runner, machine):
        if runner.state == 0:
            # evaluate the operator subexpression
            machine.schedule(self.fun, runner.env,
                             ValueCtx(runner.context.duplicate))
            runner.clos = None
        elif runner.state <= len(self.args):
            self.set_closure(runner, machine)
            # evaluate the operand subexpressions
            machine.schedule(self.args[runner.state - 1], runner.env,
                             AddressCtx(runner.context.duplicate))
        elif runner.state == 1 + len(self.args):
            self.set_closure(runner, machine)
            # call the function
            match runner.clos:
                case Closure(name, params, ret_mode, reqs, body, clos_env):
                    if len(params) != len(self.args):
                        error(self.location, 'wrong number of arguments, expected '
                              + str(len(params)) + ' not ' + str(len(self.args)))
                    runner.params = params
                    runner.body_env = clos_env.copy()
                    runner.args = runner.results[1:]
                    # TODO: check that the captured free vars have
                    # enough permission. (See fail_capture2.rte.)

                    # Bind the parameters to their arguments.
                    for param, arg in zip(params, runner.args):
                        param.bind(arg, runner.body_env, machine.memory, self.location)

                    machine.push_frame()
                    if machine.current_thread.pause_on_call:
                        machine.pause = True
                        machine.current_thread.pause_on_call = False
                    if tracing_on():
                        print('calling function ' + runner.clos.name)
                    # This treatment of the duplicate context is problematic
                    # wrt. separate compilation.
                    # Instead it needs to be declared.
                    duplicate = runner.context.duplicate
                    machine.schedule(body, runner.body_env,
                                     ValueCtx(duplicate=duplicate),
                                     return_mode=ret_mode)
                    if debug_mode() == 'n':
                        if machine.pause:
                            machine.pause = False
                            runner.pause_on_finish = True
                case _:
                    error(self.location, 'expected function in call, not '
                          + str(runner.clos))
        else:
            # return from the function:
            # deallocate the parameters
            for (param, arg) in zip(runner.params, runner.args):
                param.dealloc(machine.memory, arg, runner.body_env,
                              runner.clos.body.location)

            if runner.return_value is None:
                runner.return_value = Void()
            if isinstance(runner.context, ValueCtx):
                if runner.clos.return_mode == 'value':
                    result = Result(True, runner.return_value)
                elif runner.clos.return_mode == 'address':
                    val = machine.memory.read(runner.return_value, self.location)
                    if runner.context.duplicate:
                        result = Result(True,
                                        val.duplicate(runner.return_value.get_permission(),
                                                      self.location))
                        runner.return_value.kill(machine.memory, self.location)
                    else:
                        result = Result(False, val)  # experimental
                else:
                    raise Exception('unrecognized return_mode: '
                                    + runner.clos.return_mode)
            elif isinstance(runner.context, AddressCtx):
                if runner.clos.return_mode == 'value':
                    result = Result(True, machine.memory.allocate(runner.return_value))
                elif runner.clos.return_mode == 'address':
                    if runner.context.duplicate:
                        result = Result(True, runner.return_value.duplicate(Fraction(1, 1),
                                                                            self.location))
                        runner.return_value.kill(machine.memory, self.location)
                    else:
                        result = Result(False, runner.return_value)
                else:
                    raise Exception('unrecognized return_mode: '
                                    + runner.clos.return_mode)
            else:
                error(self.location, 'unknown context ' + repr(runner.context))
            machine.finish_expression(result, self.location)


# ========================================================================
@dataclass
class Return(Stmt):
    arg: Exp
    __match_args__ = ("arg",)

    def __str__(self):
        return "return " + str(self.arg) + ";"

    def __repr__(self):
        return str(self)

    def free_vars(self):
        return self.arg.free_vars()

    def const_eval(self, env):
        new_arg = self.arg.const_eval(env)
        return Return(self.location, new_arg)

    def type_check(self, env, ret_type):
        arg_type, new_arg = self.arg.type_check(env, 'write_rhs')
        cast_arg = make_cast(new_arg, arg_type, ret_type)
        return Return(self.location, cast_arg)

    def step(self, runner, machine):
        if runner.state == 0:
            if runner.return_mode == 'value':
                context = ValueCtx(runner.context.duplicate)
            elif runner.return_mode == 'address':
                context = AddressCtx(runner.context.duplicate)
            machine.schedule(self.arg, runner.env, context)
        else:
            if runner.context.duplicate:
                runner.return_value = \
                    runner.results[0].value.duplicate(1, self.location)
            else:
                runner.return_value = runner.results[0].value
            machine.finish_statement(self.location)


# ========================================================================
@dataclass
class Lambda(Exp):
    params: list[Param]
    captures: list[Param]
    return_mode: str  # 'value' or 'address'
    requirements: list[AST]
    body: Stmt
    name: str = "lambda"
    __match_args__ = ("params", "captures", "return_mode", "requirements",
                      "body", "name")

    def __str__(self):
        return "lambda " \
               + "(" + ", ".join([str(p) for p in self.params]) + ") " \
               + "[" + ", ".join([str(p) for p in self.captures]) + "] " \
               + ", ".join(str(req) for req in self.requirements) \
               + " " + str(self.body)

    def __repr__(self):
        return str(self)

    def free_vars(self):
        params = set([p.ident for p in self.params])
        return self.body.free_vars() - params

    def const_eval(self, env):
        new_params = [p.with_type(simplify(p.type_annot, env)) for p in self.params]
        new_captures = [p.with_type(simplify(p.type_annot, env)) \
                        for p in self.captures]
        body_env = env.copy()
        for p in new_params:
            if p.ident in body_env.keys():
                del body_env[p.ident]
        new_body = self.body.const_eval(body_env)
        return Lambda(self.location, new_params, new_captures, self.return_mode,
                      self.requirements, new_body, self.name)

    def type_check(self, env, ctx):
        # TODO: update to deal with explicit captures.
        body_env = copy_type_env(env)
        for p in self.params:
            body_env[p.ident] = StaticVarInfo(p.type_annot, None,
                                              ProperFraction(), p)
        new_reqs = []
        for req in self.requirements:
            new_req = req.declare_type(body_env, {})
            new_reqs.append(new_req)
        ret_type, new_body = self.body.type_check(body_env)
        if ret_type == None:
            ret_type = VoidType(self.location)

        return FunctionType(self.location,
                            tuple(),
                            tuple((p.kind, p.type_annot) for p in self.params),
                            ret_type,
                            tuple()), \
               Lambda(self.location, self.params, self.captures, self.return_mode,
                      new_reqs, new_body, self.name)

    def step(self, runner, machine):
        clos_env = {}
        free = self.free_vars()
        if tracing_on():
            print('free vars of ' + self.name + ': ' + str(free))

        # handle explicit captures
        for param in self.captures:
            if not param.ident in runner.env.keys():
                error(self.location, 'in lambda, cannot capture undefined variable '
                      + param.ident)
            arg = Result(False, runner.env[param.ident])
            param.bind(arg, clos_env, machine.memory, self.location)
            free = free - set([param.ident])

        # the default is to capture with 1/2 permission
        for x in free:
            if not x in runner.env.keys():
                error(self.location, 'in lambda, undefined free variable ' + x)
            v = runner.env[x]
            clos_env[x] = v.duplicate(Fraction(1, 2), self.location)

        clos = Closure(self.name, self.params, self.return_mode,
                       self.requirements, self.body, clos_env)
        if isinstance(runner.context, ValueCtx):
            result = clos
        elif isinstance(runner.context, AddressCtx):
            result = machine.memory.allocate(clos)
        else:
            error(self.location, 'function not allowed in this context')
        machine.finish_expression(Result(True, result), self.location)
