from dataclasses import dataclass
from ast_base import *


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
            error(loc, 'path field ' + str(i) + ' is not in record '
                  + str(self))
          front = self.fields[:i]
          back = self.fields[i+1:]
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
