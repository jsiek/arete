from values import *
from ast_types import *
from abstract_syntax import make_cast
import math

compare_ops = {'less': lambda x, y: x < y,
               'less_equal': lambda x, y: x <= y,
               'greater': lambda x, y: x > y,
               'greater_equal': lambda x, y: x >= y}


# TODO: move most of these out into separate files.

def eval_prim(op, vals, machine, location):
    match op:
        case 'breakpoint':
            machine.pause = True
            set_debug(True)
            return Void()
        case 'exit':
            exit(vals[0])
        case 'input':
            return Number(int(input()))
        case 'print':
            print(vals[0])
            return Void()
        case 'copy':
            return vals[0].duplicate(1, location)
        case 'equal':
            left, right = vals
            return Boolean(left.equals(right))
        case 'not_equal':
            left, right = vals
            return Boolean(not left.equals(right))
        case 'add':
            left, right = vals
            l = to_number(left, location)
            r = to_number(right, location)
            return Number(l + r)
        case 'sub':
            left = to_number(vals[0], location)
            right = to_number(vals[1], location)
            return Number(left - right)
        case 'mul':
            left = to_number(vals[0], location)
            right = to_number(vals[1], location)
            return Number(left * right)
        case 'div':
            left = to_number(vals[0], location)
            right = to_number(vals[1], location)
            return Number(Fraction(left, right))
        case 'int_div':
            left = to_number(vals[0], location)
            right = to_number(vals[1], location)
            return Number(left // right)
        case 'mod':
            left = to_number(vals[0], location)
            right = to_number(vals[1], location)
            return Number(left % right)
        case 'neg':
            val = to_number(vals[0], location)
            return Number(- val)
        case 'sqrt':
            val = to_number(vals[0], location)
            return Number(int(math.sqrt(val)))
        case 'and':
            left = to_boolean(vals[0], location)
            right = to_boolean(vals[1], location)
            return Boolean(left and right)
        case 'or':
            left = to_boolean(vals[0], location)
            right = to_boolean(vals[1], location)
            return Boolean(left or right)
        case 'not':
            val = to_boolean(vals[0], location)
            return Boolean(not val)
        case 'join':
            ptr1, ptr2 = vals
            ptr = ptr1.duplicate(1, location)
            ptr.transfer(1, ptr2, location)
            return ptr
        case 'permission':
            ptr = vals[0]
            if not isinstance(ptr, Pointer):
                error(location, "permission operation requires pointer, not "
                      + str(ptr))
            return Number(ptr.permission)
        case 'upgrade':
            ptr = vals[0]
            b = ptr.upgrade(location)
            return Boolean(b)
        case cmp if cmp in compare_ops.keys():
            left, right = vals
            l = to_number(left, location)
            r = to_number(right, location)
            return Boolean(compare_ops[cmp](l, r))
        case _:
            return get_primitive_interp(op)(vals, machine, location)


prim_types = {'add': FunctionType(None, [], [IntType(None), IntType(None)], IntType(None), []),
              'sub': FunctionType(None, [], [IntType(None), IntType(None)], IntType(None), []),
              'mul': FunctionType(None, [], [IntType(None), IntType(None)], IntType(None), []),
              'div': FunctionType(None, [], [IntType(None), IntType(None)], IntType(None), []),
              'int_div': FunctionType(None, [], [IntType(None), IntType(None)], IntType(None), []),
              'mod': FunctionType(None, [], [IntType(None), IntType(None)], IntType(None), []),
              'neg': FunctionType(None, [], [IntType(None)], IntType(None), []),
              'sqrt': FunctionType(None, [], [IntType(None)], IntType(None), []),
              'and': FunctionType(None, [], [BoolType(None), BoolType(None)], BoolType(None), []),
              'or': FunctionType(None, [], [BoolType(None), BoolType(None)], BoolType(None), []),
              'not': FunctionType(None, [], [BoolType(None)], BoolType(None), [])}


def type_check_prim(location: Meta, op: str, arg_types: list[Type], args: list[Exp]) -> tuple[Type,list[Exp]]:
    arg_types = [unfold(arg_ty) for arg_ty in arg_types]
    match op:
        case op if op in prim_types.keys():
            match prim_types[op]:
                case FunctionType(_, ps, rt, _):
                    if len(arg_types) != len(ps):
                        error(location, op + ' operator, incorrect number of arguments ' + len(arg_types))
                    for param_t, arg_t in zip(ps, arg_types):
                        require_consistent(arg_t, param_t, 'in ' + op, location)
                    new_args = [make_cast(arg, arg_t, param_t) for (arg, arg_t, param_t) in zip(args, arg_types, ps)]
                    return rt, new_args
        case 'breakpoint':
            assert len(arg_types) == 0
            return VoidType(location), []
        case 'copy':
            assert len(arg_types) == 1
            return arg_types[0], args
        case 'equal':
            assert len(arg_types) == 2
            if not consistent(arg_types[0], arg_types[1]):
                error(location, 'equal operator, '
                      + str(arg_types[0]) + ' not consistent with '
                      + str(arg_types[1]))
            common = join(arg_types[0], arg_types[1])
            new_args = [make_cast(arg, arg_t, common) for arg, arg_t in zip(args, arg_types)]
            return BoolType(location), new_args
        case 'not_equal':
            assert len(arg_types) == 2
            require_consistent(arg_types[0], arg_types[1], 'in !=', location)
            common = join(arg_types[0], arg_types[1])
            new_args = [make_cast(arg, arg_t, common) for arg, arg_t in zip(args, arg_types)]
            return BoolType(location), new_args
        case 'exit':
            assert len(arg_types) == 1
            require_consistent(arg_types[0], IntType(location), 'in exit', location)
            return VoidType(location), [make_cast(args[0], arg_types[0], IntType(location))]
        case 'input':
            assert len(arg_types) == 0
            return IntType(location), []
        case 'print':
            assert len(arg_types) == 1
            require_consistent(arg_types[0], IntType(location), 'in print',
                               location)
            return VoidType(location), [make_cast(args[0], arg_types[0], IntType(location))]
        case 'null':
            assert len(arg_types) == 0
            return PointerType(location, AnyType(location)), []
        case 'is_null':
            assert len(arg_types) == 1
            assert isinstance(arg_types[0], PointerType) \
                   or isinstance(arg_types[0], AnyType)
            return BoolType(location), args
        case 'join':
            assert len(arg_types) == 2
            # assert isinstance(arg_types[0], PointerType) \
            #   or isinstance(arg_types[0], ArrayType) \
            #   or isinstance(arg_types[0], AnyType)
            # assert isinstance(arg_types[1], PointerType) \
            #   or isinstance(arg_types[1], ArrayType) \
            #   or isinstance(arg_types[1], AnyType)
            require_consistent(arg_types[0], arg_types[1], 'in join', location)
            return join(arg_types[0], arg_types[1]), args
        case 'permission':
            assert len(arg_types) == 1
            # assert isinstance(arg_types[0], PointerType) \
            #   or isinstance(arg_types[0], ArrayType) \
            #   or isinstance(arg_types[0], AnyType)
            return RationalType(location), args
        case 'upgrade':
            assert len(arg_types) == 1
            # assert isinstance(arg_types[0], PointerType) \
            #   or isinstance(arg_types[0], ArrayType) \
            #   or isinstance(arg_types[0], AnyType)
            return BoolType(location), args
        case cmp if cmp in compare_ops.keys():
            assert len(arg_types) == 2
            require_consistent(arg_types[0], IntType(location), 'in ' + cmp, location)
            require_consistent(arg_types[1], IntType(location), 'in ' + cmp, location)
            new_args = [make_cast(arg, arg_t, IntType(location)) for arg, arg_t in zip(args, arg_types)]
            return BoolType(location), new_args
        case _:
            return get_primitive_type_check(op)(arg_types, location)


def const_eval_prim(loc, op, args):
    match op:
        case 'div':
            if is_constant(args[0]) and is_constant(args[1]):
                left = to_number(eval_constant(args[0]), loc)
                right = to_number(eval_constant(args[1]), loc)
                return Frac(loc, Fraction(left, right))
            else:
                return PrimitiveCall(loc, op, args)
        case _:
            return PrimitiveCall(loc, op, args)


@dataclass
class PrimitiveCall(Exp):
    op: str
    args: list[Exp]
    __match_args__ = ("op", "args")

    def __str__(self):
        return self.op + \
               "(" + ", ".join([str(arg) for arg in self.args]) + ")"

    def __repr__(self):
        return str(self)

    def free_vars(self):
        return set().union(*[arg.free_vars() for arg in self.args])

    def const_eval(self, env):
        op = self.op
        args = self.args
        new_args = [arg.const_eval(env) for arg in args]
        return const_eval_prim(self.location, op, new_args)

    def type_check(self, env, ctx):
        if tracing_on():
            print("starting to type checking " + str(self))
        arg_types = []
        new_args = []
        for arg in self.args:
            arg_type, new_arg = arg.type_check(env, 'none')
            arg_types.append(arg_type)
            new_args.append(new_arg)
        if tracing_on():
            print("checking primitive " + str(self.op))
        ret, cast_args = type_check_prim(self.location, self.op, arg_types, new_args)
        if tracing_on():
            print("finished type checking " + str(self))
            print("type: " + str(ret))
        return ret, PrimitiveCall(self.location, self.op, cast_args)

    def step(self, runner, machine):
        if runner.state < len(self.args):
            if self.op in set(['upgrade', 'permission']):
                dup = False
            else:
                dup = True
            machine.schedule(self.args[runner.state], runner.env,
                             ValueCtx(dup))
        else:
            result = eval_prim(self.op, [res.value for res in runner.results],
                               machine, self.location)
            if isinstance(runner.context, AddressCtx):
                # join produces an address, no need to allocate
                if self.op != 'join':
                    result = machine.memory.allocate(result)
            machine.finish_expression(Result(True, result), self.location)
