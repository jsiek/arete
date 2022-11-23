#
# This file defines the language features related to modules in Arete,
# which includes
# * module values,
# * module definitions,
# * imports, and
# * member access.

from dataclasses import dataclass
from abstract_syntax import Int
from variables_and_binding import Param
from ast_base import *
from ast_types import *
from values import Pointer, Result, delete_env
from interfaces_and_impls import InterfaceImplInfo, ImplReq
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
      return 'module ' + self.name + '(' + str(id(self)) + ')' + '{' + ','.join([x + '=' + str(v) for x,v in self.exports.items()]) + '}'
    
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
        + '  exports ' + ", ".join(str(ex) for ex in self.exports) + '\n{\n' \
        + '\n'.join([str(d) for d in self.body]) + '\n}\n'
  
  def __repr__(self):
    return str(self)

  def const_eval(self, env):
      body_env = env.copy()
      new_body = []
      for d in self.body:
          new_body += d.const_eval(body_env)
      return [ModuleDef(self.location, self.name, self.exports, new_body)]

  def declare_type(self, env):
    body_env = env.copy()
    member_info = {}
    for d in self.body:
      new_members = d.declare_type(body_env)
      member_info |= { x: info for x,info in new_members.items()}
      body_env |= new_members
    for ex in self.exports:
      if isinstance(ex, str) and not ex in member_info:
          error(self.location, 'during type checking, export ' + str(ex) + ' not defined in module')
      elif isinstance(ex, ImplReq):
        ex.search_impl(ex.impl_types, member_info, self.location)
        
    return {self.name: StaticVarInfo(ModuleType(self.location, member_info),
                                     None, ProperFraction())}
    
  def type_check(self, env):
    if tracing_on():
        print('type check ' + str(self) + '\nin ' + str(env))
    body_env = copy_type_env(env)
    members = {}
    for d in self.body:
      new_members = d.declare_type(body_env)
      members |= new_members
      body_env |= new_members
    new_body = []
    for d in self.body:
      new_body += d.type_check(body_env)
    new_exports = []
    for ex in self.exports:
      if isinstance(ex,str) and isinstance(members[ex], StaticVarInfo):
        new_exports.append(ex)
      elif isinstance(ex, ImplReq):
        witness = ex.search_impl(ex.impl_types, members, self.location)
        new_exports.append(witness.ident)
    return [ModuleDef(self.location, self.name, new_exports, new_body)]
    
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

    
@dataclass
class Import(Decl):
  module: Exp
  imports: list[Any]
  __match_args__ = ("module", "imports")
  
  def __str__(self):
    return 'from ' + str(self.module) + ' import ' \
        + ', '.join(str(im) for im in self.imports) + ';'

  def __repr__(self):
    return str(self)

  def const_eval(self, env):
      new_module = self.module.const_eval(env)
      return [Import(self.location, new_module, self.imports)]

  def declare_type(self, env):
    mod, new_mod = self.module.type_check(env, 'none')
    mod = unfold(mod)
    if isinstance(mod, ModuleType):
      self.module_type = mod
      results = {}
      for x in self.imports:
        if isinstance(x, str):
          if not x in mod.member_info.keys():
            static_error(decl.location, "in import, no " + x
                         + " in " + str(module))
          results[x] = mod.member_info[x]
        elif isinstance(x, ImplReq):
          witness = x.search_impl(x.impl_types, mod.member_info, self.location)
          if x.iface_name in results.keys():
            iface_info = results[x.iface_name]
          elif x.iface_name in env.keys():
            iface_info = env[x.iface_name]
          else:
            error(self.location, "unknown interface " + x.iface_name)
          new_info = iface_info.extend([(x.impl_types, witness)])
          results[x.iface_name] = new_info
        else:
          error(self.location, "unknown kind of import " + repr(x))
      return results
    else:
      static_error(self.location, "in import, expected a module, not "
                   + str(mod))
    
  def type_check(self, env):
    mod_type, new_module = self.module.type_check(env, 'none')
    # erase the imports of interfaces
    new_imports = []
    for x in self.imports:
      if isinstance(x,str):
        info = self.module_type.member_info[x]
        if isinstance(info, StaticVarInfo):
          new_imports.append(x)
      elif isinstance(x, ImplReq):
        witness = x.search_impl(x.impl_types, self.module_type.member_info,
                                self.location)
        new_imports.append(witness.ident)
    return [Import(self.location, new_module, new_imports)]

  def declare(self, env, mem):
    for x in self.imports:
      if isinstance(x, str):
        env[x] = mem.allocate(Void())
      elif isinstance(x, ImplReq):
        pass
      
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.module, runner.env, AddressCtx())
    else:
      mod_ptr = runner.results[0].value
      # we don't duplicate modules, so we shouldn't kill them on finish
      runner.results[0].temporary = False
      mod = machine.memory.read(mod_ptr, self.location)
      for x in self.imports:
        if isinstance(x, str):
          if x in mod.exports.keys():
            val = machine.memory.read(mod.exports[x], self.location)
            dup = val.duplicate(mod.exports[x].get_permission, self.location)
            machine.memory.write(runner.env[x], dup, self.location)
          else:
            error(self.location, 'module does not export ' + x)
        elif isinstance(x, ImplReq):
          pass
                        
      if tracing_on():
          print('** about to finish import')
      machine.finish_definition(self.location)
      if tracing_on():
          print('** finish import is complete')


@dataclass
class ModuleMember(Exp):
  arg: Exp
  field: str
  __match_args__ = ("arg", "field")
  
  def __str__(self):
      return str(self.arg) + "." + self.field
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
      return self.arg.free_vars()

  def const_eval(self, env):
      new_arg = self.arg.const_eval(env)
      return ModuleMember(self.location, new_arg, self.field)
  
  def type_check(self, env, ctx):
    mod_type, new_arg = self.arg.type_check(env, ctx)
    mod_type = unfold(mod_type)
    if not (isinstance(mod_type, ModuleType) \
            or isinstance(mod_type, AnyType)):
        static_error(self.location, "expected a module, not " + str(mod_type))
    if not self.field in mod_type.member_info.keys():
        static_error(self.location, "module " + str(self.arg)
                     + " does not contain " + self.field)
    return mod_type.member_info[self.field].type, \
        ModuleMember(self.location, new_arg, self.field)
      
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env, AddressCtx())
    else:
      mod_ptr = runner.results[0].value
      mod = machine.memory.read(mod_ptr, self.location)
      if not isinstance(mod, Module):
        error(self.location, "expected a module, not " + str(mod))
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
        
