from abstract_syntax import *
from dataclasses import dataclass
from parser import parse, set_filename
from typing import List, Set, Dict, Tuple, Any
from fractions import Fraction
import numbers
import sys
import copy
from utilities import *
from values import *

def writable(frac):
    return frac == Fraction(1, 1)

def readable(frac):
    return Fraction(0, 1) < frac and frac < Fraction(1, 1)

def none(frac):
    return frac == Fraction(0, 1)

def check_permission(frac: Fraction, kind: str):
    if kind == 'write':
        return writable(frac)
    elif kind == 'read':
        return readable(frac)
    elif kind == 'none':
        return none(frac)
    else:
        raise Exception('unrecognized permission kind: ' + str(kind))

def permission_to_fraction(priv):
    if priv == 'write':
        return Fraction(1, 1)
    elif priv == 'read':
        return Fraction(1, 2)
    elif priv == 'none':
        return Fraction(0, 1)
    else:
        raise Exception('unrecognized permission: ' + priv)
    
trace = False
next_address = 0

def generate_graphviz(env, mem):
    result = 'digraph {\n'
    # nodes
    for var, val in env.items():
        if isinstance(val, Pointer):
            result += val.node_name() + '[label="' \
                + var + ':' + val.node_label() + '"];\n'
    for addr, vals in mem.items():
        result += 'struct' + str(addr) + ' [shape=record,label="' \
            + str(addr) + ':|' \
            + '|'.join(['<' + val.node_name() + '>' + val.node_label() for val in vals]) \
            + '"];\n'
    # edges
    for var, val in env.items():
        if isinstance(val, Pointer):
            if not (val.address is None):
                result += val.node_name() + ' -> ' \
                    + 'struct' + str(val.address) + ';\n'
    for addr, vals in mem.items():
        for val in vals:
            if isinstance(val, Pointer) and not (val.address is None):
                result += 'struct' + str(addr) + ':' + val.node_name() \
                    + ' -> ' + 'struct' + str(val.address) + ';\n'
    result += '}\n'
    return result

def log_graphviz(env, mem):
    global graph_number
    filename = "env_mem_" + str(graph_number) + ".dot"
    graph_number += 1
    file = open(filename, 'w')
    file.write(generate_graphviz(env, mem))
    file.close()
    print('log graphviz: ' + filename)

def allocate(vals, mem):
    global next_address
    addr = next_address
    next_address += 1
    mem[addr] = vals
    ptr = Pointer(True, addr, Fraction(1,1), None)
    if trace:
        print('allocated new pointer ' + str(ptr))
    return ptr

def read(ptr, index, mem, location, dup):
    if not isinstance(ptr, Pointer):
        error(location, 'in read expected a pointer, not ' + str(ptr))
    if none(ptr.permission):
        error(location, 'pointer does not have read permission: ' + str(ptr))
    # whether to copy here or not?
    # see tests/fail_indirect_write
    if dup:
        retval = mem[ptr.address][index].duplicate(ptr.permission)
    else:
        retval = mem[ptr.address][index]
    if False:
        print('read from ' + str(ptr) + '[' + str(index) + ']')
        print('    value: ' + str(mem[ptr.address][index]))
        print('    producing: ' + str(retval))
    return retval
    #return mem[ptr.address]

def write(ptr, index, val, mem, location):
    if not isinstance(ptr, Pointer):
        error(location, 'in write expected a pointer, not ' + str(ptr))
    if not writable(ptr.permission):
        error(location, 'pointer does not have write permission: ' + str(ptr))
    mem[ptr.address][index].kill(mem, location)
    if val.temporary:
        mem[ptr.address][index] = val
    else:
        mem[ptr.address][index] = val.duplicate(1)
    mem[ptr.address][index].temporary = False

def delete(ptr, mem, location):
    match ptr:
      case Pointer(tmp, addr, priv):
        if trace:
            print('delete ' + str(ptr))
        if not writable(priv):
            error(location, 'delete needs writable pointer, not ' + str(ptr))
        if not addr in mem.keys():
            error(location, 'already deleted address ' + str(addr))
        for val in mem[addr]:
            val.kill(mem, location)
        del mem[addr]
    
def call_function(fun, args, env, mem, location):
    f = interp_exp(fun, env, mem)
    match f:
      case Closure(tmp, params, body, clos_env):
        vals = [interp_init(arg, env, mem, param.kind) \
                for (arg,param) in zip(args,params)]
        body_env = clos_env.copy()
        var_priv_vals = [(p.ident, p.kind, val) for p,val in zip(params, vals)]
        declare_locals([p.ident for p in params], body_env)
        allocate_locals(var_priv_vals, body_env, location)
        if trace:
            print('call ' + str(Call(location, fun, args)))
            print()
            
        try:
          retval = interp_stmt(body, body_env, mem)
        except Exception as ex:
          raise Exception(error_header(location) + ' in call ' + str(Call(location, fun, args)) + '\n' + str(ex))
        
        if trace:
            print('deallocate params from call to ' + str(fun))
        deallocate_locals([p.ident for p in params], body_env, mem, location)
        if trace:
            print('killing temporary operator from call to ' + str(fun))
        kill_temp(f, mem, location)
        for val in vals:
            kill_temp(val, mem, location)
        if trace:
            print('return from ' + str(fun) + ' with ' + str(retval))
            print(env)
            print(mem)
            log_graphviz(env, mem)
            print()
        if trace:
            print('finished call ' + str(Call(location, fun, args)))
        return retval
      case _:
        error(location, 'expected function in call, not ' + repr(f))
    
def interp_init(init, env, mem, privilege):
    match init:
      case Initializer(loc, percent, arg):
        if percent == 'default':
            if privilege == 'read':
                percentage = Fraction(1,2)
            elif privilege == 'write':
                percentage = Fraction(1,1)
            else:
                error(init.location, "unexpected privilege " + privilege)
        else:
            percentage = to_number(interp_exp(percent, env, mem), loc)
        val = interp_exp(arg, env, mem)
        return val.init(percentage, init.location)
      case _:
        error(init.location, 'in interp_init, expected an initializer, not '
              + repr(init))

def to_number(val, location):
    match val:
      case Number(tmp, value):
        return value
      case _:
        error(location, 'expected an integer, not ' + str(val))

def to_boolean(val, location):
    match val:
      case Boolean(tmp, value):
        return value
      case _:
        error(location, 'expected a boolean, not ' + str(val))

compare_ops = { 'less': lambda x, y: x < y,
                'less_equal': lambda x, y: x <= y,
                'greater': lambda x, y: x > y,
                'greater_equal': lambda x, y: x >= y}

def eval_prim(op, vals, mem, location):
    match op:
      case 'equal':
        left, right = vals
        retval = Boolean(True, left.equals(right))
        kill_temp(left, mem, location)
        kill_temp(right, mem, location)
        return retval
      case 'not_equal':
        left, right = vals
        retval = Boolean(True, not left.equals(right))
        kill_temp(left, mem, location)
        kill_temp(right, mem, location)
        return retval
      case 'add':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(True, left + right)
      case 'sub':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(True, left - right)
      case 'mul':
        left = to_number(vals[0], location)
        right = to_number(vals[0], location)
        return Number(True, left * right)
      case 'div':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(True, Fraction(left, right))
      case 'neg':
        val = to_number(vals[0], location)
        return Number(True, - val)
      case 'and':
        left = to_boolean(vals[0], location)
        right = to_boolean(vals[1], location)
        return Boolean(True, left and right)
      case 'or':
        left = to_boolean(vals[0], location)
        right = to_boolean(vals[1], location)
        return Boolean(True, left or right)
      case 'not':
        val = to_boolean(vals[0], location)
        return Boolean(True, not val)
      case 'null':
        # fraction is 1/1 because null has all of nothing! -Jeremy
        return Pointer(True, None, Fraction(1,1), None)
      case 'is_null':
        ptr = vals[0]
        match ptr:
          case Pointer(tmp, addr, priv):
            retval = Boolean(True, addr is None)
          case _:
            retval = Boolean(True, False)
        kill_temp(ptr, mem, location)
        return retval
      case 'split':
        ptr = vals[0]
        ptr1 = ptr.duplicate(Fraction(1, 2))
        ptr2 = ptr.duplicate(Fraction(1, 1))
        return allocate([ptr1, ptr2], mem)
      case 'join':
        ptr1, ptr2 = vals
        if trace:
            print('join ' + str(ptr1) + ' with ' + str(ptr2))
        ptr = ptr1.duplicate(1)
        ptr.transfer(1, ptr2, location)
        if trace:
            print('result of join: ' + str(ptr))
        return ptr
      case cmp if cmp in compare_ops.keys():
        left, right = vals
        l = to_number(left, location)
        r = to_number(right, location)
        retval = Boolean(True, compare_ops[cmp](l, r))
        kill_temp(left, mem, location)
        kill_temp(right, mem, location)
        return retval
      case _:
        error(location, 'unknown primitive operator ' + op)
    
def interp_exp(e, env, mem, dup=True, lhs=False):
    if trace:
        print('interp_exp ' + str(e))
    match e:
      case Var(x):
        if x not in env:
            error(e.location, 'use of undefined variable ' + x)
        return env_get(env, x)
      case Int(n):
        return Number(True, n)
      case Frac(f):
        return Number(True, f)
      case Bool(b):
        return Boolean(True, b)
      case Prim('permission', args):
        ptr = interp_exp(args[0], env, mem, dup=False)
        if not isinstance(ptr, Pointer):
            error(e.location, "permission operation requires pointer, not "
                  + str(ptr))
        return Number(True, ptr.permission)
      case Prim(op, args):
        vals = [interp_exp(arg, env, mem) for arg in args]
        return eval_prim(op, vals, mem, e.location)
      case Member(arg, field):
        val = interp_exp(arg, env, mem)
        match val:
          case Module(name, members):
            if field in members.keys():
                return members[field]
            else:
                error(e.location, 'no member ' + field + ' in module ' + name)
          case _:
            error(e.location, "expected a module, not " + str(val))
      case New(inits):
        vals = [interp_init(init, env, mem, 'read') for init in inits]
        return allocate(vals, mem)
      case Array(size, arg):
        size = to_number(interp_exp(size, env, mem), e.location)
        val = interp_exp(arg, env, mem)
        vals = [val.duplicate(Fraction(1,2)) for i in range(0,size-1)]
        vals.append(val)
        return allocate(vals, mem)
      case Lambda(params, body):
        clos_env = {}
        free = body.free_vars() - set([p.ident for p in params])
        if trace:
            print('duplicating free vars of lambda: ' + str(free))
        for x in free:
            v = env_get(env, x)
            if not (v is None):
                env_init(clos_env, x, v.duplicate(Fraction(1,2)))
            else:
                clos_env[x] = env[x]
        if trace:
            print('finished interp of lambda ' + str(e))
        return Closure(True, params, body, clos_env)
      case Call(fun, args):
        return call_function(fun, args, env, mem, e.location)
      case Index(arg, index):
        ptr = interp_exp(arg, env, mem, dup=dup)
        ind = interp_exp(index, env, mem)
        if trace:
            print('indexing ptr ' + str(ptr) + '[' + str(ind) + ']')
        match ind:
          case Number(tmp, i):
            if lhs:
                retval = Offset(ptr.temporary, ptr, i)
            else:
                retval = read(ptr, i, mem, e.location, dup)
                kill_temp(ptr, mem, e.location)
                kill_temp(ind, mem, e.location)
                if trace:
                    print('index result: ' + str(retval))
            return retval
          case _:
            error(e.location, 'index must be an integer, not ' + repr(ind))
      case IfExp(cond, thn, els):
        c = to_boolean(interp_exp(cond, env, mem), cond.location)
        if c:
            return interp_exp(thn, env, mem, dup, lhs)
        else:
            return interp_exp(els, env, mem, dup, lhs)
      case Let(var, init, body):
        val = interp_init(init, env, mem, var.kind)
        body_env = env.copy()
        declare_locals([var.ident], body_env)
        var_priv_vals = [(var.ident, var.kind, val)]
        allocate_locals(var_priv_vals, body_env, e.location)
        retval = interp_exp(body, body_env, mem)
        deallocate_locals([var.ident], body_env, mem, e.location)
        return retval
      case _:
        error(e.location, 'error in interp_exp, unhandled: ' + repr(e)) 

def error_header(location):
    return '{file}:{line1}.{column1}-{line2}.{column2}: ' \
        .format(file=location.filename,
                line1=location.line, column1=location.column,
                line2=location.end_line, column2=location.end_column)
            
def error(location, msg):
    raise Exception(error_header(location) + msg)

def warning(location, msg):
    header = '{file}:{line1}.{column1}-{line2}.{column2}: ' \
        .format(file=location.filename,
                line1=location.line, column1=location.column,
                line2=location.end_line, column2=location.end_column)
    print(header + 'warning: ' + msg)

graph_number = 0

def interp_stmt(s, env, mem):
    if trace:
        print()
        print('interp_stmt ' + repr(s))
        print(env)
        print(mem)
        log_graphviz(env, mem)
        print()
    match s:
      case VarInit(var, init, body):
        val = interp_init(init, env, mem, var.kind)
        body_env = env.copy()
        declare_locals([var.ident], body_env)
        var_priv_vals = [(var.ident, var.kind, val)]
        allocate_locals(var_priv_vals, body_env, init.location)
        retval = interp_stmt(body, body_env, mem)
        deallocate_locals([var.ident], body_env, mem, s.location)
        return retval
      case Seq(first, rest):
        retval = interp_stmt(first, env, mem)
        if retval is None:
            return interp_stmt(rest, env, mem)
        else:
            return retval
      case Return(arg):
        retval = interp_exp(arg, env, mem)
        return retval.return_copy()
      case Pass():
        pass
      case Write(lhs, rhs):
        offset = interp_exp(lhs, env, mem, dup=True, lhs=True)
        val = interp_init(rhs, env, mem, 'read')
        if not isinstance(offset, Offset):
            error(s.location, "expected pointer offset on left-hand side of " 
                  + "assignment, not " + str(offset))
        write(offset.ptr, offset.offset, val, mem, s.location)
        if trace:
            print('kill offset temp')
        kill_temp(offset, mem, s.location)
        kill_temp(val, mem, s.location)
      case Transfer(lhs, percent, rhs):
        dest_ptr = interp_exp(lhs, env, mem, dup=False)
        amount = to_number(interp_exp(percent, env, mem), s.location)
        src_ptr = interp_exp(rhs, env, mem, dup=False)
        if trace:
            print('transfering ' + str(amount) + ' from ' + str(src_ptr) \
                  + ' to ' + str(dest_ptr))
        dest_ptr.transfer(amount, src_ptr, s.location)
        if trace:
            print('after, src= ' + str(src_ptr) + ' dest= ' + str(dest_ptr))
      case Expr(e):
        val = interp_exp(e, env, mem)
        kill_temp(val, mem, s.location)
      case Assert(e):
        val = to_boolean(interp_exp(e, env, mem), s.location)
        if not val:
          error(e.location, "assertion failed: " + str(e))
      case Delete(arg):
        ptr = interp_exp(arg, env, mem)
        delete(ptr, mem, s.location)
        ptr.address = None
        ptr.permission = Fraction(0,1)
        if trace:
            print(env)
            print(mem)
            print()
      case IfStmt(cond, thn, els):
        c = to_boolean(interp_exp(cond, env, mem), cond.location)
        if c:
            return interp_stmt(thn, env, mem)
        else:
            return interp_stmt(els, env, mem)
      case While(cond, body):
        while to_boolean(interp_exp(cond, env, mem), cond.location):
            retval = interp_stmt(body, env, mem)
            if not (retval is None):
                return retval
      case Block(body):
        return interp_stmt(body, env, mem)
      case _:
        raise Exception('error in interp_stmt, unhandled: ' + repr(s)) 

def declare_decl(decl, env, mem):
    match decl:
      case Import(module, imports):
        for x in imports:
            env_init(env, x, None)
      case _:
        env_init(env, decl.name, None)

def interp_decls(decls, env, mem):
    for d in decls:
        declare_decl(d, env, mem)
    for d in decls:
        interp_decl(d, env, mem)
        
def interp_decl(decl, env, mem):
    if trace:
        print('interp_decl ' + str(decl))
    match decl:
      case Global(name, rhs):
        env_set(env, name, interp_exp(rhs, env, mem))
      case Function(name, params, body):
        env_set(env, name,
                interp_exp(Lambda(decl.location, params, body), env, mem))
      case ModuleDecl(name, exports, body):
        body_env = env.copy()
        interp_decls(body, body_env, mem)
        for ex in exports:
            if not ex in body_env:
                error(decl.location, 'export ' + ex + ' not defined in module')
        mod = Module(False, name,
                       {ex: env_get(body_env, ex) for ex in exports})
        if trace:
            print('finished module ' + str(mod))
        env_set(env, name, mod)
      case Import(module, imports):
        mod = interp_exp(module, env, mem)
        if trace:
            print('import from ' + str(mod))
        if not isinstance(mod, Module):
            error(decl.location, 'import expected a module, not ' + str(mod))
        for x in imports:
            if x in mod.members.keys():
                env_set(env, x, mod.members[x]) # duplicate?
            else:
                error(decl.location, 'module does not export ' + x)
                
    
def interp(decls):
    env = {}
    mem = {}
    for d in decls:
        if isinstance(d, Function) and d.name == 'main':
            main = d
    interp_decls(decls, env, mem)
    if 'main' in env.keys():
        retval = interp_exp(Call(main.location, Var(main.location, 'main'), []),
                            env, mem)
    else:
        raise Exception('program is missing a main function')

    if trace:
        print(env)
        print(mem)
        print()
    if len(mem) > 0:
        print('result: ' + str(retval.value))
        error(main.location, 'memory leak, memory size = ' + str(len(mem))) 
    return retval

flags = set(['trace', 'fail'])

if __name__ == "__main__":
    decls = []
    for filename in sys.argv[1:]:
      if filename in flags:
          continue
      set_filename(filename)
      file = open(filename, 'r')
      expect_fail = False
      if 'fail' in sys.argv:
          expect_fail = True
      if 'trace' in sys.argv:
          trace = True
      p = file.read()
      decls += parse(p, trace)
      
    try:
        retval = interp(decls)
        if expect_fail:
            print("expected failure, but didn't, returned " + str(retval))
            exit(-1)
        else:
            if trace:
                print('result: ' + str(retval.value))
            exit(retval.value)
    except Exception as ex:
        if expect_fail:
            exit(0)
        else:
            print('unexpected failure')
            if False:
                raise ex
            else:
                print(str(ex))
                print()


