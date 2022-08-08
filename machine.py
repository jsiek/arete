
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
#   finish_expression(value)
#   finish_statement()
#   finish_and_return(value)

from dataclasses import dataclass
from typing import Any
import random
import sys

from abstract_syntax import *
from desugar import desugar_decls
from utilities import *
from parser import parse, set_filename
from type_check import type_check_decls
from const_eval import const_eval_decls

@dataclass
class Action:
    ast: AST
    state: int
    results: list[(Value,Context)] # results of subexpressions
    return_value: Value  # result of `return` statement
    return_mode: str     # value or address
    context: Context     # rvalue/lvalue/etc.
    env: dict[str,Value]
    
    
@dataclass
class Frame:
    todo: list[Action]

@dataclass(eq=False)
class Thread:
    stack: list[Frame]
    result: Value        # None if not finished
    parent: Any
    num_children: int
    
@dataclass
class Machine:
  memory: Memory
  threads: list[Thread]
  current_thread: Thread
  main_thread: Thread
  result: Value

  def run(self, decls):
      self.main_thread = Thread([], None, None, 0)
      self.current_thread = self.main_thread
      self.threads = [self.main_thread]
      self.push_frame()
      
      env = {}
      for d in decls:
        if isinstance(d, Function) and d.name == 'main':
          main = d
        declare_decl(d, env, self.memory)
      for d in reversed(decls):
        self.schedule(d, env, return_mode='-no-return-mode-')
      self.loop()

      self.threads = [self.main_thread]
      self.push_frame()
      loc = main.location
      call_main = Call(loc, Var(loc, 'main'), [])
      self.schedule(call_main, env, ValueCtx(Fraction(1,2)),
                    return_mode='-no-return-mode-')
      self.loop()
      if tracing_on():
          print('** finished program')
      if tracing_on():
        print('memory: ' + str(self.memory))
        print('killing top-level env: ' + str(env))
        log_graphviz('top', env, self.memory.memory)
      delete_env('top', env, self.memory, loc)
      if tracing_on():
        print('top-level env: ' + str(env))
        log_graphviz('top', env, self.memory.memory)

      if self.memory.size() > 0:
          if tracing_on():
              print('final memory:')
              print(self.memory)
          print('program result: ' + str(self.result))
          error(main.location, 'memory leak, memory size = '
                + str(self.memory.size()))
      return self.result

  def loop(self):
      while len(self.threads) > 0:
          t = random.randint(0, len(self.threads)-1)
          self.current_thread = self.threads[t]
          # case current_thread is finished
          if len(self.current_thread.stack) == 0:
            if self.current_thread.num_children == 0:
              self.threads.remove(self.current_thread)
              if not self.current_thread.parent is None:
                  self.current_thread.parent.num_children -= 1
              if self.current_thread == self.main_thread:
                  self.result = self.current_thread.result
            continue
          # case current_thread has work to do
          frame = self.current_frame()
          if len(frame.todo) > 0:
            action = self.current_action()
            if tracing_on():
              print(error_header(action.ast.location))
              print('stepping ' + repr(action))
            action.ast.step(action, self)
            if tracing_on() and len(frame.todo) > 0:
              log_graphviz('top', self.current_action().env, self.memory.memory)
              print(machine.memory)
              print()
            #machine.memory.compute_fractions()
            action.state += 1
          else:
            self.current_thread.stack.pop()

  # Call schedule to start the evaluation of an AST node.
  # Returns the new action.
  def schedule(self, ast, env, context=ValueCtx(Fraction(1,2)),
               return_mode=None):
      return_mode = self.current_action().return_mode if return_mode is None \
                    else return_mode
      action = Action(ast, 0, [], None, return_mode, context, env)
      self.current_frame().todo.append(action)
      return action

  # Call finish_expression to signal that the current expression
  # action is finished and register the value it produced with the
  # previous action.
  def finish_expression(self, result, location):
      if tracing_on():
          print('finish_expression ' + str(result))
          print(self.memory)
      for (p,ctx) in self.current_action().results:
        if not isinstance(ctx, ObserveCtx):
          p.kill(machine.memory, location)
      context = self.current_action().context
      self.current_frame().todo.pop()
      if len(self.current_frame().todo) > 0:
          self.current_action().results.append((result, context))
      elif len(self.current_thread.stack) > 1:
          self.pop_frame(result)
      else:
          if tracing_on():
              print('finished thread ' + str(result))
          self.current_thread.result = result

  # Call finish_statement to signal that the current statement action is done.
  # Propagates the return value if there is one.
  def finish_statement(self, location):
      retval = self.current_action().return_value
      if tracing_on():
          print('finish_statement ' + str(retval))
      for (p,ctx) in self.current_action().results:
        if not isinstance(ctx, ObserveCtx):
          p.kill(machine.memory, location)
      self.current_frame().todo.pop()
      if len(self.current_frame().todo) > 0:
        self.current_action().return_value = retval
      elif len(self.current_thread.stack) > 1:
        self.pop_frame(retval)
      else:
        self.result = retval

  def finish_declaration(self, location):
    for (p,ctx) in self.current_action().results:
      if not isinstance(ctx, ObserveCtx):
        p.kill(machine.memory, location)
    self.current_frame().todo.pop()
        
  def push_frame(self):
      frame = Frame([])
      self.current_thread.stack.append(frame)

  def pop_frame(self, val):
      self.current_thread.stack.pop()
      self.current_action().return_value = val

  def current_frame(self):
      return self.current_thread.stack[-1]

  def current_action(self):
      return self.current_frame().todo[-1]

  def spawn(self, exp: Exp, env):
      act = Action(exp, 0, [], None,
                   self.current_action().return_mode, # ??
                   ValueCtx(Fraction(1,1)), env)
      frame = Frame([act])
      self.current_thread.num_children += 1
      thread = Thread([frame], None, self.current_thread, 0)
      self.threads.append(thread)
      return thread
  
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
          set_trace(True)
      p = file.read()
      decls += parse(p, False)
      
    decls = desugar_decls(decls, {})
    if tracing_on():
      print('**** after desugar ****')
      print(decls)
      print()
    decls = const_eval_decls(decls, {})
    if tracing_on():
      print('**** after const_eval ****')
      print(decls)
      print()
    try:
      type_check_decls(decls, {})
      if tracing_on():
        print('**** finished type checking ****')

      machine = Machine(Memory(), [], None, None, None)
      retval = machine.run(decls)
      if expect_fail:
          print("expected failure, but didn't, returned " + str(retval))
          exit(-1)
      else:
          if tracing_on():
              print('result: ' + str(retval.value))
          exit(int(retval.value))
    except Exception as ex:
        if expect_fail:
            exit(0)
        else:
            print('unexpected failure')
            if tracing_on():
                raise ex
            else:
                print(str(ex))
                print()


