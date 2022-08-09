from values import *

def graphviz_env(label, env):
    result = 'subgraph cluster_' + label + '{\n'
    result += 'label = ' + label + ';\n'
    # nodes
    for var, val in env.items():
        if isinstance(val, Pointer):
            result += label + '_' + var + '[label="' \
                + var + ':' + val.node_label() + '"];\n'
    result += '}\n'
    # edges
    for var, val in env.items():
        if isinstance(val, Pointer):
            if not (val.address is None):
                result += label + '_' + var + ' -> ' \
                    + str(val.address) + ' [len=1];\n'
    return result
  
def generate_graphviz(label, env, mem):
    result = 'digraph {\n'
    result += 'overlap=scale\n'
    result += graphviz_env(label, env)
    # nodes
    for addr, val in mem.items():
      if not val is None: # how could it be None? bug? -Jeremy
        result += str(addr) + ' [shape=record,label="' \
            + '<base> ' + str(addr) + ': |' \
            + val.node_label() \
            + '"];\n'
    # edges
    for addr, val in mem.items():
      if isinstance(val, Pointer) and not (val.address is None):
        result += str(addr) + ' -> ' + val.node_name() + ' [len=1];\n'
      elif isinstance(val, TupleValue):
        for i, elt in zip(range(0, len(val.elts)), val.elts):
          if isinstance(elt, Pointer) and not elt.address is None \
             and elt.permission > Fraction(0,1):
            result += str(addr) + ':' + str(i) \
              + ' -> ' + elt.node_name() + ' [len=1];\n'
      elif isinstance(val, Module):
        result += graphviz_env(val.name, val.members)
    result += '}\n'
    return result

graph_number = 0
  
def log_graphviz(label, env, mem):
    global graph_number
    filename = "env_mem_" + str(graph_number) + ".dot"
    graph_number += 1
    file = open(filename, 'w')
    file.write(generate_graphviz(label, env, mem))
    file.close()
    print('log graphviz: ' + filename)
