from dataclasses import dataclass
from typing import List, Set, Dict, Tuple, Any
from lark.tree import Meta
from fractions import Fraction
from utilities import *

# Parameters

@dataclass(frozen=True)
class Param:
    location: Meta
    kind: str # read, write
    ident: str
    __match_args__ = ("kind", "ident")
    def __str__(self):
        return self.kind + " " + self.ident
    def __repr__(self):
        return str(self)

# Miscelaneous

@dataclass
class Initializer:
  location: Meta
  percentage: Exp
  arg: Exp
  __match_args__ = ("location", "percentage", "arg")
  def __str__(self):
      return str(self.percentage) + " of " + str(self.arg)
  def __repr__(self):
      return str(self)
  def free_vars(self):
      percent_fv = set() if isinstance(self.percentage, str) \
          else self.percentage.free_vars()
      return percent_fv | self.arg.free_vars()
  def step(self, action, machine):
    if action.state == 0:
      if self.percentage == 'default':
        if action.privilege == 'read':
          self.percentage = Frac(self.location, Fraction(1,2))
        elif action.privilege == 'write':
          self.percentage = Frac(self.location, Fraction(1,1))
        else:
          error(self.location, "unexpected privilege " + action.privilege)
      machine.schedule(self.percentage, action.env)
    elif action.state == 1:
      machine.schedule(self.arg, action.env)
    else:
      percent, val = action.results
      num = to_number(percent, self.location)
      machine.finish_expression(val.init(num, self.location))
      
# Expressions

@dataclass
class Call(Exp):
  fun: Exp
  args: List[Initializer]
  __match_args__ = ("fun", "args")
  def __str__(self):
      return str(self.fun) \
          + "(" + ", ".join([str(arg) for arg in self.args]) + ")"
  def __repr__(self):
      return str(self)
  def free_vars(self):
      return self.fun.free_vars() \
          | set().union(*[arg.free_vars() for arg in self.args])
  def step(self, action, machine):
    if action.state == 0:
      # evaluate subexpressions
      machine.schedule(self.fun, action.env)
    elif action.state <= len(self.args):
      clos = action.results[0]
      if not isinstance(clos, Closure):
        error(location, 'expected function in call, not ' + str(clos))
      init_act = machine.schedule(self.args[action.state - 1], action.env)
      init_act.privilege = clos.params[action.state - 1].kind
    elif action.state == len(self.args) + 1:
      # call the function
      match action.results[0]:
        case Closure(tmp, params, body, clos_env):
          action.params = params
          action.body_env = clos_env.copy()
          var_priv_vals = [(p.ident, p.kind, val) \
                           for p,val in zip(params, action.results[1:])]
          declare_locals([p.ident for p in params], action.body_env)
          allocate_locals(var_priv_vals, action.body_env, self.location)
          machine.push_frame()
          machine.schedule(body, action.body_env)
        case _:
          error(location, 'expected function in call, not '
                + str(self.fun_action.result))
    else:
      # return from the function
      deallocate_locals([p.ident for p in action.params], action.body_env,
                        machine.memory, self.location)
      for val in action.results:
          kill_temp(val, machine.memory, self.location)
      if action.return_value is None:
        action.return_value = Void(True)
      machine.finish_expression(action.return_value)

@dataclass
class Prim(Exp):
    op: str
    args: List[Exp]
    __match_args__ = ("op", "args")
    def __str__(self):
        return self.op + \
            "(" + ", ".join([str(arg) for arg in self.args]) + ")"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set().union(*[arg.free_vars() for arg in self.args])
    def step(self, action, machine):
      if action.state < len(self.args):
        machine.schedule(self.args[action.state], action.env,
                         dup=(False if self.op == 'permission' else True))
      else:
        retval = eval_prim(self.op, action.results, machine.memory,
                           self.location)
        machine.finish_expression(retval)
            
@dataclass
class Member(Exp):
    arg: Exp
    field: str
    __match_args__ = ("arg", "field")
    def __str__(self):
        return str(self.arg) + "." + self.field
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.arg, action.env)
      else:
        mod = action.results[0]
        if not isinstance(mod, Module):
          error(e.location, "expected a module, not " + str(val))
        if self.field in mod.members.keys():
          machine.finish_expression(mod.members[self.field])
        else:
          error(self.location, 'no member ' + self.field
                + ' in module ' + mod.name)
        
@dataclass
class New(Exp):
    inits: List[Initializer]
    __match_args__ = ("inits",)
    def __str__(self):
        return "new " + ", ".join([str(e) for e in self.inits])
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set().union(*[init.free_vars() for init in self.inits])
    def step(self, action, machine):
      if action.state < len(self.inits):
        init_act = machine.schedule(self.inits[action.state], action.env)
        init_act.privilege = 'read'
      else:
        machine.finish_expression(allocate(action.results, machine.memory))

@dataclass
class Array(Exp):
    size: Exp
    arg: Exp
    __match_args__ = ("size","arg")
    def __str__(self):
        return "new " + "[" + str(self.size) + "]" + str(self.arg)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.size.free_vars() | self.arg.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.size, action.env)
      elif action.state == 1:
        machine.schedule(self.arg, action.env)
      else:
        sz, val = action.results
        size = to_number(sz, self.location)
        vals = [val.duplicate(Fraction(1,2)) for i in range(0,size-1)]
        vals.append(val)
        machine.finish_expression(allocate(vals, machine.memory))
      
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
    def step(self, action, machine):
        if self.ident not in action.env:
            error(self.location, 'use of undefined variable ' + self.ident)
        machine.finish_expression(env_get(action.env, self.ident))

@dataclass
class Int(Exp):
    value: int
    __match_args__ = ("value",)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set()
    def step(self, action, machine):
        machine.finish_expression(Number(True, self.value))

@dataclass
class Frac(Exp):
    value: Fraction
    __match_args__ = ("value",)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set()
    def step(self, action,  machine):
        machine.finish_expression(Number(True, self.value))
    
@dataclass
class Bool(Exp):
    value: bool
    __match_args__ = ("value",)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set()
    def step(self, action, machine):
        machine.finish_expression(Boolean(True, self.value))
    
@dataclass
class Index(Exp):
    arg: Exp
    index: Exp
    __match_args__ = ("arg", "index")
    def __str__(self):
        return str(self.arg) + "[" + str(self.index) + "]"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars() | self.index.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.arg, action.env)
      elif action.state == 1:
        machine.schedule(self.index, action.env)
      else:
        ptr, ind = action.results
        match ind:
          case Number(tmp, i):
            if action.lhs:
                retval = Offset(ptr.temporary, ptr, i)
            else:
                retval = read(ptr, i, machine.memory, self.location, action.dup)
                kill_temp(ptr, machine.memory, self.location)
                kill_temp(ind, machine.memory, self.location)
            machine.finish_expression(retval)
          case _:
            error(self.location, 'index must be an integer, not ' + repr(ind))
        
@dataclass
class Lambda(Exp):
    params: List[Param]
    body: Stmt
    __match_args__ = ("params", "body")
    def __str__(self):
        return "function " \
            + "(" + ", ".join([str(p) for p in self.params]) + ")" \
            + " { " + str(self.body) + " }"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.body.free_vars() - set([p.ident for p in self.params])
    def step(self, action, machine):
        clos_env = {}
        free = self.body.free_vars() - set([p.ident for p in self.params])
        for x in free:
            v = env_get(action.env, x)
            if not (v is None):
                env_init(clos_env, x, v.duplicate(Fraction(1,2)))
            else:
                clos_env[x] = action.env[x]
        clos = Closure(True, self.params, self.body, clos_env)
        machine.finish_expression(clos)
    
@dataclass
class IfExp(Exp):
    cond: Exp
    thn: Exp
    els: Exp
    __match_args__ = ("cond", "thn", "els")
    def __str__(self):
        return "(" + str(self.cond) + "?" + str(self.thn) \
            + " : " + str(self.els) + ")"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.cond.free_vars() | self.thn.free_vars() \
            | self.els.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.cond, action.env)
      elif action.state == 1:
        if to_boolean(action.results[0], self.location):
          machine.schedule(self.thn, action.env)
        else:
          machine.schedule(self.els, action.env)
      elif action.state == 2:
        machine.finish_expression(action.results[1])
    
@dataclass
class Let(Exp):
    var: Param
    init: Initializer
    body: Exp
    __match_args__ = ("var", "init", "body")
    def __str__(self):
        return "var " + str(self.var) + " = " + str(self.init) + ";\n" \
            + str(self.body)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.init.free_vars() | \
            (self.body.free_vars() - set([self.var.ident]))
    def step(self, action, machine):
      if action.state == 0:
        init_act = machine.schedule(self.init, action.env)
        init_act.privilege = self.var.kind
      elif action.state == 1:
        val = action.results[0]
        action.body_env = action.env.copy()
        declare_locals([self.var.ident], action.body_env)
        var_priv_vals = [(self.var.ident, self.var.kind, val)]
        allocate_locals(var_priv_vals, action.body_env, self.location)
        machine.schedule(self.body, action.body_env)
      else:
        deallocate_locals([self.var.ident], action.body_env, machine.memory,
                          self.location)
        machine.finish_expression(action.results[1])

@dataclass
class FutureExp(Exp):
  arg: Exp
  __match_args__ = ("arg",)
  def __str__(self):
    return "future " + str(self.arg)
  def __repr__(self):
    return str(self)
  def free_vars(self):
    return self.arg.free_vars()
  def step(self, action, machine):
    thread = machine.spawn(self.arg, action.env)
    retval = Future(True, thread)
    machine.finish_expression(retval)

@dataclass
class Await(Exp):
  arg: Exp
  __match_args__ = ("arg",)
  def __str__(self):
    return "await " + str(self.arg)
  def __repr__(self):
    return str(self)
  def free_vars(self):
    return self.arg.free_vars()
  def step(self, action, machine):
    if action.state == 0:
      machine.schedule(self.arg, action.env)
    else:
      future = action.results[0]
      if not future.thread.result is None:
        machine.finish_expression(future.thread.result)
  
    
# Statements

@dataclass
class Seq(Stmt):
  first: Stmt
  rest: Stmt
  __match_args__ = ("first", "rest")
  def __str__(self):
    if False:
      return str(self.first) + "\n" + str(self.rest)
    else:
      return str(self.first) + "..."
  def __repr__(self):
    return str(self)
  def free_vars(self):
    return self.first.free_vars() | self.rest.free_vars()
  def step(self, action, machine):
    if action.state == 0:
      machine.schedule(self.first, action.env)
    elif not action.return_value is None:
      machine.finish_statement()
    else:
      machine.finish_statement()
      machine.schedule(self.rest, action.env)
    
@dataclass
class VarInit(Exp):
    var: Param
    init: Initializer
    body: Stmt
    __match_args__ = ("var", "init", "body")
    def __str__(self):
      if False:
        return "var " + str(self.var) + " = " + str(self.init) + ";\n" \
            + str(self.body)
      else:
        return "var " + str(self.var) + " = " + str(self.init) + "; ..."
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.init.free_vars() \
            | (self.body.free_vars() - set([self.var.ident]))
    def step(self, action, machine):
      if action.state == 0:
        init_act = machine.schedule(self.init, action.env)
        init_act.privilege = self.var.kind
      elif action.state == 1:
        val = action.results[0]
        action.body_env = action.env.copy()
        declare_locals([self.var.ident], action.body_env)
        var_priv_vals = [(self.var.ident, self.var.kind, val)]
        allocate_locals(var_priv_vals, action.body_env, self.init.location)
        machine.schedule(self.body, action.body_env)
      else:
        deallocate_locals([self.var.ident], action.body_env,
                          machine.memory, self.location)
        machine.finish_statement()

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
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.arg, action.env)
      else:
        action.return_value = action.results[0].return_copy()
        machine.finish_statement()
    
@dataclass
class Write(Stmt):
    lhs: Exp
    rhs: Initializer
    __match_args__ = ("lhs", "rhs")
    def __str__(self):
        return str(self.lhs) + " = " + str(self.rhs) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.lhs.free_vars() | self.rhs.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.lhs, action.env, lhs=True)
      elif action.state == 1:
        init_act = machine.schedule(self.rhs, action.env)
        init_act.privilege = 'read'
      else:
        offset, val = action.results
        if not isinstance(offset, Offset):
            error(self.location,
                  "expected pointer offset on left-hand side of " 
                  + "assignment, not " + str(offset))
        write(offset.ptr, offset.offset, val, machine.memory, self.location)
        kill_temp(offset, machine.memory, self.location)
        kill_temp(val, machine.memory, self.location)
        machine.finish_statement()

@dataclass
class Transfer(Stmt):
    lhs: Exp
    percent: Exp
    rhs: Exp
    __match_args__ = ("lhs", "percent", "rhs")
    def __str__(self):
        return str(self.lhs) + " <= " + str(self.percent) + " of " \
            + str(self.rhs) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.lhs.free_vars() | self.percent.free_vars() \
            | self.rhs.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.lhs, action.env, dup=False)
      elif action.state == 1:
        machine.schedule(self.percent, action.env)
      elif action.state == 2:
        machine.schedule(self.rhs, action.env, dup=False)
      else:
        dest_ptr, amount, src_ptr = action.results
        percent = to_number(amount, self.location)
        dest_ptr.transfer(percent, src_ptr, self.location)
        machine.finish_statement()
    
@dataclass
class Delete(Stmt):
    arg: Exp
    __match_args__ = ("arg",)
    def __str__(self):
        return "delete " + str(self.arg) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.arg, action.env)
      else:
        ptr = action.results[0]
        delete(ptr, machine.memory, self.location)
        ptr.address = None
        ptr.permission = Fraction(0,1)
        machine.finish_statement()
    
@dataclass
class Expr(Stmt):
    exp: Exp
    __match_args__ = ("exp",)
    def __str__(self):
        return str(self.exp) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.exp.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.exp, action.env)
      else:
        machine.finish_statement()

@dataclass
class Assert(Stmt):
    exp: Exp
    __match_args__ = ("exp",)
    def __str__(self):
        return "assert " + str(self.exp) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.exp.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.exp, action.env)
      else:
        val = to_boolean(action.results[0], self.location)
        if not val:
          error(e.location, "assertion failed: " + str(e))
        machine.finish_statement()

@dataclass
class IfStmt(Stmt):
    cond: Exp
    thn: Stmt
    els: Stmt
    __match_args__ = ("cond", "thn", "els")
    def __str__(self):
      if False:
        return "if " + "(" + str(self.cond) + ")\n" + str(self.thn) \
            + "else " + str(self.els)
      else:
        return "if " + "(" + str(self.cond) + ") ..."
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.cond.free_vars() | self.thn.free_vars() \
            | self.els.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.cond, action.env)
      elif action.state == 1:
        if to_boolean(action.results[0], self.location):
          machine.schedule(self.thn, action.env)
        else:
          machine.schedule(self.els, action.env)
      else:
        machine.finish_statement()

@dataclass
class While(Stmt):
    cond: Exp
    body: Stmt
    __match_args__ = ("cond", "body")
    def __str__(self):
        return "while " + "(" + str(self.cond) + ")\n" + str(self.body) 
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.cond.free_vars() | self.body.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.cond, action.env)
      elif action.state == 1:
        c = to_boolean(action.results[0], self.cond.location)
        if c:
          machine.schedule(self, action.env)
          machine.schedule(self.body, action.env)
        else:
          machine.finish_statement()
      else:
        machine.finish_statement()
    
@dataclass
class Pass(Stmt):
    def __str__(self):
        return "pass"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set()
    def step(self, action, machine):
      machine.finish_statement()

@dataclass
class Block(Stmt):
    body: Exp
    __match_args__ = ("body",)
    def __str__(self):
        return "{\n" + str(self.body) + "\n}\n"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.body.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.body, action.env)
      else:
        machine.finish_statement()
    
# Declarations
    
@dataclass
class Global(Exp):
    name: str
    rhs: Exp
    __match_args__ = ("name", "rhs")
    def __str__(self):
        return "var " + str(self.name) + " = " + str(self.rhs) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return init.free_vars()
    def local_vars(self):
        return set([var.ident])
    
@dataclass
class Function(Decl):
    name: str
    params: List[Param]
    body: Exp
    __match_args__ = ("name", "params", "body")
    def __str__(self):
        return "function " + self.name \
            + "(" + ", ".join([str(p) for p in self.params]) + ")" \
            + " { " + str(self.body) + " }"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return body.free_vars() - set([p.ident for p in self.params])

@dataclass
class ModuleDecl(Decl):
    name: str
    exports: List[str]
    body: Stmt
    __match_args__ = ("name", "exports", "body")
    def __str__(self):
        return 'module ' + self.name + '\n'\
            + '  exports ' + ", ".join(ex for ex in self.exports) + ' {\n' \
            + str(self.body) + '\n}\n'
    def __repr__(self):
        return str(self)

@dataclass
class Import(Decl):
    module: Exp
    imports: List[str]
    __match_args__ = ("module", "imports")
    def __str__(self):
        return 'from ' + str(self.module) + ' import ' \
            + ', '.join(im for im in self.imports) + ';\n'
    def __repr__(self):
        return str(self)
    
