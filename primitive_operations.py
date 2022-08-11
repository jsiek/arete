from values import *

compare_ops = { 'less': lambda x, y: x < y,
                'less_equal': lambda x, y: x <= y,
                'greater': lambda x, y: x > y,
                'greater_equal': lambda x, y: x >= y}

def eval_prim(op, vals, machine, location):
    match op:
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
      case 'null':
        return Pointer(None, [], Fraction(1,1), None)
      case 'is_null':
        ptr = vals[0]
        match ptr:
          case Pointer(addr, path, priv):
            return Boolean(addr is None)
          case _:
            return Boolean(False)
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
        
