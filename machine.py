
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

trace = False

@dataclass
class Action:
    ast: AST
    state: int
    env: dict[str,Value]
    dup: bool # duplicate the value? default is True
    lhs: bool # left-hand side of an assignment (Write), default is False
    results: list[Value] # results of subexpressions
    return_value: Value # result of `return` statement
    privilege: str
    
@dataclass
class Frame:
    todo: list[Action]

@dataclass
class Thread:
    stack: list[Frame]
    result: Value        # None if not finished
    parent: Any
    num_children: int
    
@dataclass
class Machine:
  memory: dict[int,Value]
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
        self.schedule(d, env)
      self.loop()

      self.threads = [self.main_thread]
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
            if trace:
              print('len(frame.todo) = ' + str(len(frame.todo)))
            action = self.current_action()
            if trace:
              print('stepping ' + repr(action))
              print(machine.memory)
            action.ast.step(action, self)
            action.state += 1
          else:
            self.current_thread.stack.pop()

  # Call schedule to start the evaluation of an AST node.
  # Returns the new action.
  def schedule(self, ast, env, dup=True, lhs=False):
      if trace:
          print('scheduling ' + str(ast))
      action = Action(ast, 0, env, dup, lhs, [], None, '???')
      self.current_frame().todo.append(action)
      return action

  # Call finish_expression to signal that the current expression
  # action is finished and register the value it produced with the
  # previous action.
  def finish_expression(self, val):
      if trace:
          print('finish_expression ' + str(val))
      self.current_frame().todo.pop()
      if len(self.current_frame().todo) > 0:
          self.current_action().results.append(val)
      elif len(self.current_thread.stack) > 1:
          self.pop_frame(val)
      else:
          if trace:
              print('finished thread ' + str(val))
          self.current_thread.result = val

  # Call finish_statement to signal that the current statement action is done.
  # Propagates the return value if there is one.
  def finish_statement(self):
      retval = self.current_action().return_value
      if trace:
          print('finish_statement ' + str(retval))
      self.current_frame().todo.pop()
      if len(self.current_frame().todo) > 0:
        self.current_action().return_value = retval
      elif len(self.current_thread.stack) > 1:
        self.pop_frame(retval)
      else:
        self.result = retval

  def finish_declaration(self):
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
      act = Action(exp, 0, env, True, False, [], None, 'read')
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
          trace = True
      p = file.read()
      decls += parse(p, trace)
      
    decls = desugar_decls(decls, {})
    if trace:
      print('**** after desugar ****')
      print(decls)
      print()
    decls = const_eval_decls(decls, {})
    if trace:
      print('**** after const_eval ****')
      print(decls)
      print()
    type_check_decls(decls, {})
      
    
    machine = Machine({}, [], None, None, None)
    try:
      retval = machine.run(decls)
      if expect_fail:
          print("expected failure, but didn't, returned " + str(retval))
          exit(-1)
      else:
          if trace:
              print('result: ' + str(retval.value))
          exit(retval.value)
    except Exception as ex:
        if expect_fail:
            exit(0)
        else:
            print('unexpected failure')
            if trace:
                raise ex
            else:
                print(str(ex))
                print()


