#
# This file defines the language features related to modules in Arete,
# which includes
# * module values,
# * module definitions,
# * imports, and
# * member access.

from dataclasses import dataclass
from abstract_syntax import Param, Int
from ast_base import *
from ast_types import *
from values import Pointer, Result, delete_env
from utilities import *

@dataclass(eq=False)
class Module(Value):
    name: str
    exports: dict[str, Pointer] # only the exports
    members: dict[str, Pointer] # all the members
    __match_args__ = ("name", "exports")
    def duplicate(self, percentage, loc):
        error(loc, 'modules may not be copied')
        # members_copy = {x: val.duplicate(percentage, loc) \
        #                 for x,val in self.members.items()}
        # exports_copy = {x: members_copy[x] for x in self.exports.keys()}
        # return Module(self.name, exports_copy, self.members)
    def __str__(self):
      return self.name + '(' + str(id(self)) + ')' + '{' + ','.join([x + '=' + str(v) for x,v in self.exports.items()]) + '}'
    def __repr__(self):
        return str(self)
    def kill(self, mem, location, progress=set()):
        if tracing_on():
          print('*** killing module ' + self.name + ' (' + str(id(self)) + ')')
        delete_env(self.name, self.members, mem, location)
        if tracing_on():
          print('*** finished killing module ' + self.name + ' (' + str(id(self)) + ')')
    def clear(self, mem, location, progress=set()):
        for val in self.members.values():
          val.clear(mem, location, progress)
    def node_name(self):
        return str(self.name)
    def node_label(self):
        return str(self.name)

@dataclass
class ModuleDef(Decl):
  name: str
  exports: list[str]
  body: list[Decl]
  __match_args__ = ("name", "exports", "body")
  
  def __str__(self):
    return 'module ' + self.name + '\n'\
        + '  exports ' + ", ".join(ex for ex in self.exports) + ' {\n' \
        + '\n'.join([str(d) for d in self.body]) + '\n}\n'
  
  def __repr__(self):
    return str(self)
  
  def step(self, runner, machine):
    if runner.state == 0:
      runner.body_env = {}
      for d in self.body:
        d.declare(runner.body_env, machine.memory)
    if runner.state < len(self.body):
      machine.schedule(self.body[runner.state], runner.body_env)
    else:
      for ex in self.exports:
        if not ex in runner.body_env:
          error(self.location, 'export ' + ex + ' not defined in module')
      mod = Module(self.name,
                   {ex: runner.body_env[ex] for ex in self.exports},
                   runner.body_env)
      machine.memory.memory[runner.env[self.name].address] = mod
      machine.finish_definition(self.location)

  def declare_type(self, env, output):
    member_types = {}
    for d in self.body:
      d.declare_type(env, member_types)
    for ex in self.exports:
      if not ex in member_types:
        error(self.location, 'export ' + ex + ' not defined in module')
    env[self.name] = ModuleType(self.location, member_types)
    output[self.name] = env[self.name]
    
  def type_check(self, env):
    body_env = env.copy()
    members = {}
    for d in self.body:
      d.declare_type(body_env, members)
    for d in self.body:
      d.type_check(body_env)
    
    
@dataclass
class Import(Decl):
  module: Exp
  imports: list[str]
  __match_args__ = ("module", "imports")
  
  def __str__(self):
    return 'from ' + str(self.module) + ' import ' \
        + ', '.join(im for im in self.imports) + ';'

  def __repr__(self):
    return str(self)

  def declare(self, env, mem):
    for x in self.imports:
        env[x] = mem.allocate(Void())
      
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.module, runner.env, AddressCtx())
    else:
      mod_ptr = runner.results[0].value
      # we don't duplicate modules, so we shouldn't kill them on finish
      runner.results[0].temporary = False
      mod = machine.memory.read(mod_ptr, self.location)
      # mod = machine.memory.read(mod_ptr, self.location)      
      for x in self.imports:
        if x in mod.exports.keys():
          val = machine.memory.read(mod.exports[x], self.location)
          dup = val.duplicate(mod.exports[x].get_permission, self.location)
          machine.memory.write(runner.env[x], dup, self.location)
        else:
          error(self.location, 'module does not export ' + x)
      if tracing_on():
          print('** about to finish import')
      machine.finish_definition(self.location)
      if tracing_on():
          print('** finish import is complete')
      
  def declare_type(self, env, output):
    mod = self.module.type_check(env)
    mod = unfold(mod)
    if isinstance(mod, ModuleType):
      for x in self.imports:
          if not x in mod.member_types.keys():
            error(decl.location, "in import, no " + x
                  + " in " + str(module))
          env[x] = mod.member_types[x]
          output[x] = env[x]
    else:
      error(self.location, "in import, expected a module, not " + str(mod))
    
  def type_check(self, env):
    pass

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
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env, AddressCtx())
    else:
      mod_ptr = runner.results[0].value
      mod = machine.memory.read(mod_ptr, self.location)
      if not isinstance(mod, Module):
        error(self.location, "expected a module, not " + str(val))
      if self.field in mod.exports.keys():
        ptr = mod.exports[self.field]
        if isinstance(runner.context, ValueCtx):
          val = machine.memory.read(ptr, self.location)
          result = Result(True, val.duplicate(ptr.get_permission(),
                                              self.location))
        elif isinstance(runner.context, AddressCtx):
          result = Result(False, ptr)
        machine.finish_expression(result, self.location)
      else:
        error(self.location, 'no member ' + self.field
              + ' in module ' + mod.name)
        
  def type_check(self, env):
    mod_type = self.arg.type_check(env)
    mod_type = unfold(mod_type)
    if not isinstance(mod_type, ModuleType):
        error(self.location, "expected a module, not " + str(mod_type))
    if not self.field in mod_type.member_types.keys():
        error(self.location, "module " + str(self.arg) + " does not contain "
              + self.field)
    return mod_type.member_types[self.field]
        
      
