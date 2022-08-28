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
  members: dict[str,Type]

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

@dataclass
class Interface(Decl):
  name: str
  type_params: list[str]
  members: list[tuple[str,Type]]
  __match_args__ = ("name", "type_params", "members")

  def __str__(self):
    return 'interface ' + self.name + '(' + ', '.join(self.type_params) + ')' \
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
    body_env = env.copy()
    for x in self.type_params:
      body_env[x] = TypeVar(self.location, x)
    mems = {x: simplify(t, body_env) for x,t in self.members}
    self.iface_info = InterfaceInfo(self.name, self.type_params, mems)
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
      + '(' + ', '.join(str(self.impl_types)) + ');'
    
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
      print('type checking ' + str(self))
    iface_impl_info = env[self.iface_name]
    member_types = {}
    for x,e in self.assignments:
      member_types[x] = e.type_check(env)
    
    # check that this Impl is satisfied
    subst = { x:t for x,t in zip(iface_impl_info.iface.params, self.impl_types)}
    for x,ty in iface_impl_info.iface.members.items():
      req_ty = substitute(subst, ty)
      if not x in member_types.keys():
        error(self.location, "missing requirement " + x + " for impl of "
              + self.iface_name + ' for ' + ', '.join([str(ty) for ty in self.impl_types]))
      if tracing_on():
        print('impl requirement ' + x + ' : ' + str(req_ty))
        print('has type ' + str(member_types[x]))
      if not consistent(req_ty, member_types[x]):
        error(self.location, "type of " + x + ":\n"
              + str(member_types[x])
              + "\nis not consistent with the required type:\n"
              + str(req_ty))
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
      for x in iface_impl_info.members.keys():
        if not x in members.keys():
          error(self.location, "requirement " + x
                 + " was not provided by the implementation")
      mod = Record(members)
      mod_ptr = machine.memory.allocate(mod)
      machine.memory.unchecked_write(runner.env[self.name], mod_ptr,
                                     self.location)
      mod_ptr.kill(machine.memory, self.location) # because write duplicates
      machine.finish_definition(self.location)

@dataclass(eq=True, frozen=True)
class ImplReq(Type):
  iface_name: str
  impl_types: tuple[Type]  # implementing type(s)
  iface: Type
  
  def __str__(self):
    return self.iface_name + '(' + \
      ', '.join([str(ty) for ty in self.impl_types]) + ');'
    
  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    pass
  
  def step(self, runner, machine):
    pass

  def declare_type(self, env, output):
    if not self.iface_name in env.keys():
      error(self.location, "undefined interface " + self.iface_name)
    iface_impl_info = env[self.iface_name]
    subst = { x:ty for x, ty in zip(iface_impl_info.iface.params,
                                    self.impl_types)}
    for x, ty in iface_impl_info.iface.members.items():
      env[x] = substitute(subst, ty)
    return ImplReq(self.location,
                   self.iface_name, self.impl_types, iface_impl_info.iface)

  def type_check(self, env):
    pass
  
