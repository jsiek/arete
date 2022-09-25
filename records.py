from dataclasses import dataclass
from ast_base import *
from ast_types import *
from utilities import AddressCtx, ValueCtx
from values import Result, duplicate_if_temporary, PointerOffset

@dataclass
class Record(Value):
    fields: dict[str,Value]

    def equals(self, other):
      if len(self.fields.keys()) == len(other.fields.keys()):
        for f in self.fields.keys():
          if self.fields[f] != other.fields[f]:
            return False
        return True
      else:
        return False
    
    def duplicate(self, percentage, loc):
      return Record({f: elt.duplicate(percentage, loc) \
                     for f,elt in self.fields.items()})
    
    def kill(self, mem, location, progress=set()):
      for elt in self.fields.values():
        elt.kill(mem, location, progress)

    def clear(self, mem, location, progress=set()):
      for elt in self.fields.values():
        elt.clear(mem, location, progress)

    def get_subobject(self, path, loc):
      if len(path) == 0:
        return self
      else:
        return self.fields[path[0]].get_subobject(path[1:], loc)

    def set_subobject(self, path, val, loc):
        if len(path) == 0:
          return val
        else:
          i = path[0]
          if not i in self.fields.keys():
            error(loc, 'path field ' + i + ' is not in record '
                  + str(self))
          new_fields = {}
          ith = self.fields[i].set_subobject(path[1:], val, loc)
          for f, elt in self.fields.items():
            if f == i:
              new_fields[f] = ith
            else:
              new_fields[f] = elt
          return Record(new_fields)
      
    def __str__(self):
        return '{' + ', '.join([f + "=" + str(elt)
                                for f,elt in self.fields.items()]) + '}'
      
    def __repr__(self):
        return str(self)
      
    def node_name(self):
        return str(self)
      
    def node_label(self):
        return '|'.join(['<' + f + '>' + elt.node_label() \
                         for f,elt in self.fields.items()])
      
    def gen_graphviz(self, addr):
      result = ''
      elt_names = []
      elt_labels = []
      for elt in self.fields.values(): # TODO
        subresult, elt_name, elt_label = elt.gen_graphviz(None)
        result += subresult
        elt_names.append(elt_name)
        elt_labels.append(elt_label)
      if addr is None:
        name = str(id(self))
        base = ''
      else:
        name = str(addr)
        base = '<base> ' + str(addr) + ': |'
      tuple_label = base \
        + '|'.join(['<' + str(i) + '>' + label \
                    for (i,label) in zip(range(0,len(elt_labels)),elt_labels)])
      # add node
      result += name + ' [shape=record,label="' + tuple_label + '"];\n'

      # add out-edges
      for i, elt_name in zip(range(0, len(elt_names)), elt_names):
        if not elt_name is None:
          result += name + ':' + str(i) + ' -> ' + elt_name + ';\n'

      return result, name, '•'

# Record Creation

@dataclass
class RecordExp(Exp):
  fields: list[tuple[str,Exp]]
  __match_args__ = ("fields",)
    
  def __str__(self):
    return "{" + ", ".join([f + "= " + str(e) for f,e in self.fields]) + "}"
    
  def __repr__(self):
    return str(self)
    
  def free_vars(self):
    return set().union(*[e.free_vars() for f,e in self.fields])

  def const_eval(self, env):
    new_fields = [(f, e.const_eval(env)) for f,e in self.fields]
    return RecordExp(self.location, new_fields)
  
  def type_check(self, env, ctx):
    field_types = {}
    new_fields = []
    for field, init in self.fields:
      init_type, new_init = init.type_check(env, 'write_rhs')
      field_types[field] = init_type
      new_fields.append((field, new_init))
    return RecordType(self.location, tuple(field_types.items())), \
           RecordExp(self.location, new_fields)

  def step(self, runner, machine):
    if runner.state < len(self.fields):
      machine.schedule(self.fields[runner.state][1], runner.env)
    else:
      vals = [res.value.duplicate(1, self.location) for res in runner.results]
      record = Record({f: v for (f,e),v in zip(self.fields, vals)})
      if isinstance(runner.context, ValueCtx):
        result = record
      elif isinstance(runner.context, AddressCtx):
        result = machine.memory.allocate(record)
      machine.finish_expression(Result(True, result), self.location)

# Field Access

@dataclass
class FieldAccess(Exp):
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
    return FieldAccess(self.location, new_arg, self.field)
    
  def type_check(self, env, ctx):
    arg_type, new_arg = self.arg.type_check(env, ctx)
    new_self = FieldAccess(self.location, new_arg, self.field)
    arg_type = unfold(arg_type)
    if isinstance(arg_type, RecordType):
        field_types = {f: t for f,t in arg_type.field_types}
        if self.field in field_types.keys():
          return field_types[self.field], new_self
        else:
          error(self.location, 'field ' + self.field
                + ' not in record ' + str(arg_type))
    elif isinstance(arg_type, AnyType):
      return AnyType(self.location), new_self
    else:
      error(self.location, 'in field access, expected a record, not '
            + str(arg_type))
      
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env,
                       AddressCtx(runner.context.duplicate))
    else:
      if isinstance(runner.context, ValueCtx):
        record_ptr = runner.results[0].value
        record = machine.memory.read(record_ptr, self.location)
        if not isinstance(record, Record):
          error(self.location, 'expected a record, not ' + str(record))
        if not self.field in record.fields.keys():
          error(self.location, 'field ' + self.field + ' not in record ' + str(record))
        val = record.fields[self.field]
        if runner.results[0].temporary:
            val = val.duplicate(record_ptr.permission, self.location)
        result = Result(runner.results[0].temporary, val)
      elif isinstance(runner.context, AddressCtx):
        if tracing_on():
            print('in FieldAccess.step, AddressCtx')
        res = duplicate_if_temporary(runner.results[0], self.location)
        ptr = res.value
        ptr_offset = PointerOffset(ptr, self.field)
        result = Result(runner.results[0].temporary, ptr_offset)
      else:
        error(self.location, 'unrecognized context ' + repr(runner.context))
      machine.finish_expression(result, self.location)

