#
# This file defines the language features for constrained generics in Arete,
# which includes
# * interface definitions,
# * impl definitions, 
# * impl requirements.

# Use Module values for witness tables?

from dataclasses import dataclass
from ast_base import *
from ast_types import *
from values import Result, Pointer
from variables_and_binding import Var
from records import Record
from utilities import *

@dataclass
class InterfaceInfo:
  name: str
  params: list[str]
  extends: list[AST]
  immediate_members: dict[str,Type]
  members: dict[str,Type]   # includes inherited members

  def copy(self):
    return self
  
  def duplicate(self, percent, loc):
    return self
  
  def kill(self, mem, loc, progress=set()):
    pass
  
  def gen_graphviz(self, addr):
    return ('','','')

  def get_subobject(self, path, loc):
      if len(path) == 0:
        return self
      else:
        error(loc, 'InterfaceInfo has no parts')

@dataclass
class InterfaceImplInfo:
  iface: InterfaceInfo
  impls: list[tuple[list[Type], Exp]]

  def copy(self):
    return InterfaceImplInfo(self.iface,
                             [(tys, e) for tys, e in self.impls])

  def duplicate(self, percent, loc):
    return self.copy()
  
@dataclass
class Interface(Decl):
  name: str
  type_params: list[str]
  extends: list[AST]
  members: list[tuple[str,Type]]
  __match_args__ = ("name", "type_params", "extends", "members")

  def __str__(self):
    return 'interface ' + self.name + '(' + ', '.join(self.type_params) + ')' \
      + ' extends ' + ', '.join([str(req) for req in self.extends]) \
      + ' {\n' \
      + '\n'.join(x + ': ' + str(t) for x,t in self.members) \
      + '}'
    
  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    pass
  
  def step(self, runner, machine):
    machine.memory.unchecked_write(runner.env[self.name],
                                   self.iface_info,
                                   self.location)
    machine.finish_definition(self.location)

  def declare_type(self, env, output):
    body_env = {x: t.copy()  for x, t in env.items()}
    for x in self.type_params:
      body_env[x] = TypeVar(self.location, x)
    immediate_mems = {x: simplify(t, body_env) for x,t in self.members}
    mems = immediate_mems.copy()
    # Add inherited members
    for req in self.extends:
      if not req.iface_name in env.keys():
        error(self.location, 'interface ' + req.iface_name + ' is not defined')
      iface_info = env[req.iface_name].iface
      subst = {x:ty for x, ty in zip(iface_info.params, req.impl_types) }
      for x, ty in iface_info.members.items():
        mems[x] = substitute(subst, ty)
    self.iface_info = InterfaceInfo(self.name, self.type_params, self.extends,
                                    immediate_mems, mems)
    env[self.name] = InterfaceImplInfo(self.iface_info, [])
    output[self.name] = env[self.name]
  
  def type_check(self, env):
    pass

@dataclass
class Impl(Decl):
  name: str
  iface_name: str
  impl_types: list[Type] # implementing type(s)
  assignments: list[tuple[str,Exp]]
  
  __match_args__ = ("name", "iface_name", "impl_types", "assignments")
  
  def __str__(self):
    return 'impl ' + self.name + ': ' + self.iface_name \
      + '(' + ', '.join(str(ty) for ty in self.impl_types) + ');'
    
  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    pass
  
  def declare_type(self, env, output):
    if not self.iface_name in env.keys():
      error(self.location, "undefined interface " + self.iface_name)
    # declare this Impl
    iface_impl_info = env[self.iface_name]
    self.impl_types = [simplify(ty, env) for ty in self.impl_types]
    iface_impl_info.impls += [(self.impl_types, Var(self.location, self.name))]
        
  def type_check(self, env):
    if tracing_on():
      print('type checking ' + str(self) + '\n'
            'in environment: ' + str(env))
    iface_impl_info = env[self.iface_name]
    member_types = {}
    for x,e in self.assignments:
      member_types[x] = e.type_check(env)

    # check that the inherited interfaces are implemented
    # TODO
      
    # check that this Impl is satisfied
    subst = { x:t for x,t in zip(iface_impl_info.iface.params, self.impl_types)}
    for x,ty in iface_impl_info.iface.immediate_members.items():
      req_ty = substitute(subst, ty)
      if not x in member_types.keys():
        error(self.location, "missing requirement " + x + " for impl of "
              + self.iface_name
              + ' for ' + ', '.join([str(ty) for ty in self.impl_types]))
      if not consistent(req_ty, member_types[x]):
        error(self.location, "type of " + x + ":\n" + str(member_types[x])
              + "\nis not consistent with the required type:\n" + str(req_ty))
    if tracing_on():
      print('finished type checking ' + str(self))
  
  def step(self, runner, machine):
    if runner.state < len(self.assignments):
      machine.schedule(self.assignments[runner.state][1], runner.env)
    else:
      iface_impl_ptr = runner.env[self.iface_name]
      iface_impl_info = machine.memory.read(iface_impl_ptr, self.location)

      # lookup all the requirements in the current environment
      # members = {}
      # for x in iface_impl_info.members.keys():
      #   if not x in runner.env.keys():
      #     error(self.location, "could not find requirement " + x
      #           + " in the current environment")
      #   members[x] = runner.env[x].duplicate(Fraction(1,2), self.location)

      members = {}
      for (f,e),res in zip(self.assignments, runner.results):
        members[f] = res.value
      for x in iface_impl_info.immediate_members.keys():
        if not x in members.keys():
          error(self.location, "requirement " + x
                 + " was not provided by the implementation")
      witness = Record(members)
      #witness_ptr = machine.memory.allocate(witness)
      machine.memory.unchecked_write(runner.env[self.name], witness,
                                     self.location)
      #witness_ptr.kill(machine.memory, self.location) # because write duplicates
      machine.finish_definition(self.location)

@dataclass(eq=True, frozen=True)
class ImplReq(Type):
  name: str
  iface_name: str
  impl_types: tuple[Type]  # implementing type(s)
  iface: Type
  
  def __str__(self):
    return self.name + ': ' + self.iface_name + '(' + \
      ', '.join([str(ty) for ty in self.impl_types]) + ')'
    
  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    pass
  
  def declare_type(self, env, output):
    if not self.iface_name in env.keys():
      error(self.location, "undefined interface " + self.iface_name)
    iface_impl_info = env[self.iface_name]
    subst = { x:ty for x, ty in zip(iface_impl_info.iface.params,
                                    self.impl_types)}
    # Bring the impl into scope
    iface_impl_info.impls += [(self.impl_types, Var(self.location, self.name))]

    # TODO: this needs to be recursive to handle deep inheritance chains.
    # Bring the inherited impls into scope
    for req in iface_impl_info.iface.extends:
      subst = {x: ty for x, ty in zip(iface_impl_info.iface.params,
                                      self.impl_types)}
      impl_types = [substitute(subst, ty) for ty in req.impl_types]
      env[req.iface_name].impls += [(impl_types, Var(self.location, req.name))]
    
    # Bring the impl members into scope
    for x, ty in iface_impl_info.iface.members.items():
      env[x] = substitute(subst, ty)
    return ImplReq(self.location, self.name, self.iface_name, self.impl_types,
                   iface_impl_info.iface)

  def satisfy_impl(self, deduced_types, env, fun_env):
    iface_impl_info = env[self.iface_name]
    req_impl_types = [substitute(deduced_types, simplify(ty, fun_env)) \
                      for ty in self.impl_types]
    if tracing_on():
      print('searching for impl of ' + self.iface_name
            + ' for ' + str(req_impl_types))
    witness_exp = None
    for impl_tys, wit_exp in iface_impl_info.impls:
      if all([t1 == t2 for t1, t2 in zip(req_impl_types, impl_tys)]):
        witness_exp = wit_exp
        break
    if witness_exp is None:
      error(self.location, 'could not find impl of ' + self.iface_name
            + ' for ' + str(req_impl_types)
            + '\nin impls:\n'
            + str(iface_impl_info.impls))
    return witness_exp    

  def bind_impl(self, witness_ptr, env, machine):
    # Bind impl name to its witness.
    env[self.name] = witness_ptr

    # Bind impl member names to their values.
    witness = machine.memory.read(witness_ptr, self.location)
    for x,val in witness.fields.items():
      dup = val.duplicate(Fraction(1,2), self.location)
      env[x] = machine.memory.allocate(dup)

