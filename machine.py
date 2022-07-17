
# machine configuration:
# memory
# thread pool
# per thread:
#   procedure call stack of frames
#   per frame:
#     todo: list of actions
#     action is an AST node, a state, and env

# API or coroutines?

# AST methods:
#   step(state, env, machine)

# Machine methods:
#   schedule(ast, env) returns the action
#   finalize(value)

from dataclasses import dataclass
from typing import Any

from interp import *
from abstract_syntax import AST

trace = False

@dataclass
class Action:
    ast: AST
    state: int
    env: dict[str,Value]
    dup: bool # default is True
    lhs: bool # default is False
    results: list[Value]
    privilege: str
    
@dataclass
class Frame:
    todo: list[Action]
    
@dataclass
class Machine:
    memory: dict[int,Value]
    stack: list[Frame]
    result: Value

    def run(self, decls):
        env = {}
        for d in decls:
            if isinstance(d, Function) and d.name == 'main':
                main = d
        interp_decls(decls, env, machine.memory)
        self.push_frame()
        loc = main.location
        call_main = Call(loc, Var(loc, 'main'), [])
        self.schedule(call_main, env)
        self.loop()
        if len(self.memory) > 0:
            error(main.location, 'memory leak, memory size = '
                  + str(len(self.memory)))
        return self.result

    def loop(self):
        i = 0
        while len(self.stack) > 0 and i < 1000:
            i += 1
            if False:
                print('configuration: ' + repr(self))
            frame = self.current_frame()
            if len(frame.todo) > 0:
                if trace:
                    print('len(frame.todo) = ' + str(len(frame.todo)))
                action = self.current_action()
                if trace:
                    print('stepping ' + repr(action))
                action.ast.step(action, self)
                action.state += 1
            else:
                self.stack.pop()
                
    # Call schedule to start the evaluation of an AST node.
    # Returns the new action.
    def schedule(self, ast, env, dup=True, lhs=False):
        if trace:
            print('scheduling ' + str(ast))
        action = Action(ast, 0, env, dup, lhs, [], '???')
        self.current_frame().todo.append(action)
        return action

    # Call finalize to signal that the current action is finished
    # and register the result value with the previous action.
    def finalize(self, val):
        if trace:
            print('finalize ' + str(val))
        self.current_frame().todo.pop()
        if len(self.current_frame().todo) > 0:
            self.current_action().results.append(val)
        elif len(self.stack) > 1:
            self.pop_frame(val)
        else:
            if trace:
                print('finished execution ' + str(val))
            self.result = val

    # Call finished to signal that the current statement action is done.
    def finished(self):
        self.current_frame().todo.pop()
            
    def push_frame(self):
        frame = Frame([])
        self.stack.append(frame)

    def pop_frame(self, val):
        self.stack.pop()
        self.current_action().results.append(val)
        
    def current_frame(self):
        return self.stack[-1]

    def current_action(self):
        return self.current_frame().todo[-1]

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
    
    machine = Machine({}, [], None)
    retval = machine.run(decls)
    if trace:
        print('result: ' + str(retval))
    exit(retval.value)
