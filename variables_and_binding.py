#
# This file defines the language features related to variables in Arete,
# which includes
# * variable (occurences)
# * binding expressions
# * binding statements
#
# Of course, function parameters are also related to variables, but
# functions are defined in `functions.py`.

from dataclasses import dataclass
from ast_base import *
from ast_types import *
from values import *
from utilities import *
from abstract_syntax import make_cast


# ===========================================================================
# Parameters

@dataclass(frozen=True)
class Param:
    location: Meta
    kind: str  # let, var, inout, sink, set
    privilege: str  # read, write # OBSOLETE?
    ident: str
    type_annot: Type
    __match_args__ = ("privilege", "ident")

    # Return a Param that's the same except for the type annotation.
    def with_type(self, ty):
        return Param(self.location, self.kind, self.privilege, self.ident, ty)

    def const_eval(self, env):
        type_annot = simplify(self.type_annot, env)
        return Param(self.location, self.kind, self.privilege,
                     self.ident, type_annot)

    def bind_type(self, env):
        if self.kind == 'let':
            # let-bound variables are unsinkable.
            # This differs from Val, where let-bound locals are sinkable
            # if they are not aliased. Val's let-bound parameters are unsinkable.
            state = ProperFraction()
        elif self.kind == 'inout' or self.kind == 'var':
            state = FullFraction()
        elif self.kind == 'ref':
            # state = ProperFraction()
            # warning: optimistic! TODO
            state = FullFraction()
        env[self.ident] = StaticVarInfo(self.type_annot, None, state, self)

    # At runtime, bind the result to this parameter/variable
    def bind(self, res: Result, env, memory, loc):
        val = res.value
        if not val.is_pointer():
            error(loc, 'for binding, expected a pointer, not ' + str(val))
        if tracing_on():
            print('binding ' + self.ident + ' to ' + str(val))

        if self.kind == 'let':
            res.permission = val.get_permission()

        if res.temporary:
            # what if val is a PointerOffset??
            if self.kind == 'let':
                env[self.ident] = val.duplicate(Fraction(1, 2), loc)
            else:
                env[self.ident] = val

        if self.kind == 'let':
            if (not val.get_address() is None) \
                    and val.get_permission() == Fraction(0, 1):
                error(loc, 'let binding requires non-zero permission, not '
                      + str(val))
            if not res.temporary:
                env[self.ident] = val.duplicate(Fraction(1, 2), loc)
            env[self.ident].kill_when_zero = True

        elif self.kind == 'var' or self.kind == 'inout':
            success = val.upgrade(loc)
            if not success:
                error(loc, ' binding ' + str(self) + ' requires permission 1/1, not '
                      + str(val))
            if not res.temporary:
                env[self.ident] = val.duplicate(Fraction(1, 1), loc)
                if self.kind == 'var':
                    val.kill(memory, loc)
            if self.kind == 'var':
                env[self.ident].no_give_backs = True

        # The `ref` kind is not in Val. It doesn't guarantee any
        # read/write ability and it does not guarantee others
        # won't mutate. Unlike `var`, it does not consume the
        # initializing value. I'm not entirely sure if `ref`
        # is needed, but it has come in handy a few times.
        elif self.kind == 'ref':
            if not res.temporary:
                env[self.ident] = val.duplicate(Fraction(1, 1), loc)

        else:
            error(loc, 'unrecognized kind of parameter: ' + self.kind)

    # This binding is going out of scope, so deallocate it.
    def dealloc(self, memory, arg, env, loc):
        ptr = env[self.ident]
        if self.kind == 'inout':
            self.inout_end_of_life(ptr, arg.value, loc)
        elif self.kind == 'let':  # UNDER CONSTRUCTION
            self.let_end_of_life(ptr, arg, loc)
        if tracing_on():
            print('deallocating binding ' + self.ident)
        ptr.kill(memory, loc)

    def inout_end_of_life(self, ptr, source, loc):
        if tracing_on():
            print('inout end-of-life ' + self.ident)
        if ptr.get_permission() != Fraction(1, 1):
            error(loc, 'failed to restore inout variable '
                  + 'to full\npermission by the end of its scope')
        if source.get_address() is None:
            error(loc, "inout can't return ownership because"
                  + " previous owner died")
        source.transfer(Fraction(1, 1), ptr, loc)

    def let_end_of_life(self, ptr, source, loc):
        if tracing_on():
            print('let end-of-life ' + self.ident
                  + '\nptr: ' + str(ptr)
                  + '\nsource: ' + str(source))
        # This happens in tests/for_in_seq.rte, don't know why.
        # The ptr is already null. -Jeremy
        # if source.permission == Fraction(1,1):
        if ptr.get_address() is None:
            return
        if ptr.get_permission() != source.permission / 2:
            error(loc, 'failed to restore let-bound variable '
                  + 'to\noriginal permission of\n\t'
                  + str(source.permission / 2)
                  + '\nby the end of its scope, only have\n\t'
                  + str(ptr.permission))
        if source.value.get_address() is None:
            error(loc, "let can't return ownership because"
                  + " previous owner died")
        source.value.transfer(Fraction(1, 1), ptr, loc)

    def __str__(self):
        if self.kind is None:
            return self.privilege + ' ' + self.ident + ': ' + str(self.type_annot)
        else:
            return self.kind + ' ' + self.ident + ': ' + str(self.type_annot)

    def __repr__(self):
        return str(self)


# ===========================================================================
@dataclass(frozen=True)
class NoParam:
    location: Meta

    def bind(self, res: Result, env, mem, loc):
        pass

    def dealloc(self, memory, arg, env, loc):
        pass


# ===========================================================================
# The borrowed_vars global is for communicating variables bound
# to inout parameters in function calls.

borrowed_vars = dict()


def clear_borrowed_vars():
    global borrowed_vars
    borrowed_vars = dict()


def add_borrowed_var(var, info):
    global borrowed_vars
    borrowed_vars = borrowed_vars | {var: info.copy()}


def get_borrowed_vars():
    return borrowed_vars


# ===========================================================================
@dataclass
class Var(Exp):
    ident: str
    __match_args__ = ("ident",)

    def __str__(self):
        return self.ident

    def __repr__(self):
        return str(self)

    def free_vars(self):
        return set([self.ident])

    def const_eval(self, env):
        if self.ident in env:
            return env[self.ident]
        else:
            return self

    def type_check(self, env, ctx):
        if self.ident not in env:
            static_error(self.location, 'use of undefined variable ' + self.ident)
        info = env[self.ident]
        if not hasattr(info, 'state'):
            print('bad type env info: ' + str(info))
            exit(-1)

        if ctx == 'let':
            if not static_readable(info.state):
                static_error(self.location,
                             "don't have read permission for " + self.ident
                             + ", only " + str(info.state))
            add_borrowed_var(self.ident, info)
            info.state = ProperFraction()
        elif ctx == 'var':
            if info.state != FullFraction():
                static_error(self.location,
                             "dont' have write permission for " + self.ident
                             + ", only " + str(info.state))
            info.state = Dead()
        elif ctx == 'inout':
            if info.state != FullFraction():
                static_error(self.location,
                             "don't have full permission for " + self.ident
                             + ", only " + str(info.state))
            add_borrowed_var(self.ident, info)
            info.state = EmptyFraction()
        elif ctx == 'write_lhs':
            if info.state != FullFraction():
                static_error(self.location,
                             "don't have write permission for " + self.ident
                             + ", only " + str(info.state))
        elif ctx == 'write_rhs':
            if not static_readable(info.state):
                static_error(self.location,
                             "don't have read permission for " + self.ident
                             + ", only " + str(info.state))
            # problem: see tests/array.rte
            # env[self.ident].state = EmptyFraction()
        elif ctx == 'none':
            pass
        elif ctx == 'ref':
            # UNDER CONSTRUCTION
            if not static_readable(info.state):
                static_error(self.location,
                             "don't have read permission for " + self.ident
                             + ", only " + str(info.state))
            add_borrowed_var(self.ident, info)
            info.state = ProperFraction()  ## ??
        else:
            static_error(self.location, "unrecognized context: " + ctx)

        if info.translation is None:
            return info.type, self
        else:
            return info.type, info.translation

    def step(self, runner, machine):
        if self.ident not in runner.env:
            error(self.location, 'use of undefined variable ' + self.ident)
        ptr = runner.env[self.ident]
        if isinstance(runner.context, ValueCtx):
            val = machine.memory.read(ptr, self.location)
            if runner.context.duplicate:
                val = val.duplicate(ptr.get_permission(), self.location)
            result = Result(runner.context.duplicate, val)
        elif isinstance(runner.context, AddressCtx):
            result = Result(False, ptr)
        machine.finish_expression(result, self.location)


# ===========================================================================
# aka. let-expressions in functional languages
#
@dataclass
class BindingExp(Exp):
    param: Param
    arg: Exp
    body: Exp
    __match_args__ = ("param", "arg", "body")

    def __str__(self):
        if verbose():
            return str(self.param) + " = " + str(self.arg) + ";\n" \
                   + str(self.body)
        else:
            return str(self.param) + " = " + str(self.arg) + "; ..."

    def __repr__(self):
        return str(self)

    def free_vars(self):
        return self.arg.free_vars() \
               | (self.body.free_vars() - set([self.param.ident]))

    def const_eval(self, env):
        param = self.param
        rhs = self.arg
        body = self.body
        new_param = param.with_type(simplify(param.type_annot, env))
        new_rhs = rhs.const_eval(env)
        body_env = env.copy()
        if new_param.ident in body_env.keys():
            del body_env[new_param.ident]
        new_body = body.const_eval(body_env)
        return BindingExp(self.location, new_param, new_rhs, new_body)

    def type_check(self, env, ctx):
        rhs_type, new_arg = self.arg.type_check(env, self.param.kind)
        if not consistent(rhs_type, self.param.type_annot):
            static_error(self.arg.location,
                         'type of initializer ' + str(rhs_type)
                         + '\nis inconsistent with declared type '
                         + str(self.param.type_annot))
        cast_arg = make_cast(new_arg, rhs_type, self.param.type_annot)
        body_env = copy_type_env(env)
        self.param.bind_type(body_env)
        body_type, new_body = self.body.type_check(body_env, ctx)
        return body_type, BindingExp(self.location, self.param, cast_arg,
                                     new_body)

    def step(self, runner, machine):
        if runner.state == 0:
            machine.schedule(self.arg, runner.env, AddressCtx())
        elif runner.state == 1:
            runner.body_env = runner.env.copy()
            self.param.bind(runner.results[0], runner.body_env, machine.memory,
                            self.arg.location)
            machine.schedule(self.body, runner.body_env, runner.context)
        else:
            self.param.dealloc(machine.memory, runner.results[0],
                               runner.body_env, self.location)
            result = duplicate_if_temporary(runner.results[1], self.location)
            machine.finish_expression(result, self.location)


# ===========================================================================
# This is meant to have the same semantics as the `let`, `var`, and
# `inout` statement in Val.
@dataclass
class BindingStmt(Exp):
    param: Param
    arg: Exp
    body: Stmt
    __match_args__ = ("param", "arg", "body")

    def __str__(self):
        if verbose():
            return str(self.param) + " = " + str(self.arg) + ";\n" \
                   + str(self.body)
        else:
            return str(self.param) + " = " + str(self.arg) + "; ..."

    def __repr__(self):
        return str(self)

    def free_vars(self):
        return self.arg.free_vars() \
               | (self.body.free_vars() - set([self.param.ident]))

    def const_eval(self, env):
        param = self.param
        rhs = self.arg
        body = self.body
        new_param = param.with_type(simplify(param.type_annot, env))
        new_rhs = rhs.const_eval(env)
        body_env = env.copy()
        if new_param.ident in body_env.keys():
            del body_env[new_param.ident]
        new_body = body.const_eval(body_env)
        return BindingStmt(self.location, new_param, new_rhs, new_body)

    def type_check(self, env, ret):
        if self.param.kind == 'var':
            arg_env = env
        else:
            arg_env = copy_type_env(env)
        arg_type, new_arg = self.arg.type_check(arg_env, self.param.kind)
        if not consistent(arg_type, self.param.type_annot):
            static_error(self.arg.location, 'type of initializer ' + str(arg_type)
                         + '\nis inconsistent with declared type '
                         + str(new_param.type_annot))
        cast_arg = make_cast(new_arg, arg_type, self.param.type_annot)
        body_env = copy_type_env(arg_env)
        self.param.bind_type(body_env)
        new_body = self.body.type_check(body_env, ret)
        return BindingStmt(self.location, self.param, cast_arg, new_body)

    def step(self, runner, machine):
        if runner.state == 0:
            machine.schedule(self.arg, runner.env, AddressCtx())
        elif runner.state == 1:
            runner.body_env = runner.env.copy()
            self.param.bind(runner.results[0], runner.body_env, machine.memory,
                            self.arg.location)
            # Treat binding statements special for debugging.
            # Pretend they finish before the body runs.
            if runner.pause_on_finish:
                machine.pause = True
                runner.pause_on_finish = False
            machine.schedule(self.body, runner.body_env)
        else:
            self.param.dealloc(machine.memory, runner.results[0],
                               runner.body_env, self.location)
            machine.finish_statement(self.location)
