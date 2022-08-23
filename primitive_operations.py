from values import *
from types import *

compare_ops = { 'less': lambda x, y: x < y,
                'less_equal': lambda x, y: x <= y,
                'greater': lambda x, y: x > y,
                'greater_equal': lambda x, y: x >= y}

def eval_prim(op, vals, machine, location):
    match op:
      case 'breakpoint':
        machine.pause = True
        set_debug(True)
        return Void()
      case 'exit':
        exit(vals[0])
      case 'copy':
        return vals[0].duplicate(1, location)
      case 'len':
        tup = vals[0]
        if not isinstance(tup, TupleValue):
          error(location, "in len, expected a tuple or array not " + str(tup))
        n = len(tup.elts)
        return Number(n)
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
        right = to_number(vals[0], location)
        return Number(left * right)
      case 'div':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(Fraction(left, right))
      case 'int_div':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(left // right)
      case 'neg':
        val = to_number(vals[0], location)
        return Number(- val)
      case 'and':
        left = to_boolean(vals[0], location)
        right = to_boolean(vals[1], location)
        return Boolean(left and right)
      case 'or':
        left = to_boolean(vals[0], location)
        right = to_boolean(vals[1], location)
        return left or right
      case 'not':
        val = to_boolean(vals[0], location)
        return Boolean(not val)
      case 'split':
        ptr = vals[0]
        ptr1 = ptr.duplicate(Fraction(1, 2), location)
        ptr2 = ptr.duplicate(Fraction(1, 1), location)
        # is this allocation necessary?
        #return machine.memory.allocate(TupleValue([ptr1, ptr2]))
        return TupleValue([ptr1, ptr2])
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
        error(location, 'unknown primitive operator ' + op)    
        
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
      case 'exit':
        assert len(arg_types) == 1
        require_consistent(arg_types[0], IntType(location), 'in exit', location)
        return VoidType(location)
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
