
# machine configuration:
# memory
# thread pool
# per thread:
#   procedure call stack of frames
#   per frame:
#     todo: list of runners
#     runner is an AST node, a state, and env

# API or coroutines?

# AST methods:
#   step(state, env, machine)

# Machine methods:
#   schedule(ast, env) returns the runner
#   finish_expression(result)
#   finish_statement()
#   finish_and_return(value)

from dataclasses import dataclass
from typing import Any
import random
import sys

from abstract_syntax import *
from functions import *
from variables_and_binding import *
from tuples_and_arrays import *
from variants import *
from modules import *
from pointers import *
from utilities import *
from parser import parse, set_filename
from type_check import type_check_program
from const_eval import const_eval_decls
from memory import *
from graphviz import log_graphviz

@dataclass
class NodeRunner:
    ast: AST
    state: int
    results: list[Result] # results of subexpressions
    return_value: Value  # result of `return` statement
    return_mode: str     # value or address mode of enclosing function
    context: Context     # rvalue/lvalue/etc.
    env: dict[str,Pointer]
    pause_on_finish : bool = False # for debugger control

    def produce_value(self, val, machine, location):
      if isinstance(self.context, ValueCtx):
          result = val
      elif isinstance(self.context, AddressCtx):
          result = machine.memory.allocate(val)
      machine.finish_expression(Result(True, result), location)
        
        
@dataclass
class Frame:
    todo: list[NodeRunner]

@dataclass(eq=False)
class Thread:
    stack: list[Frame]
    return_value: Value        # None if not finished
    parent: Any
    num_children: int
    pause_on_call: bool = False # for debugger control

debug_commands = set(['e',  # print environment
                      'm',  # print memory
                      'n',  # next subexpression (don't dive into functions)
                      's',  # step subexpression (dive into functions)
                      'f',  # finish this AST node
                      'd',  # dive into this function call
                      'v',  # toggle verbose printing
                      'g',  # output a graphviz file of memory
                      'c',  # continue running the program
                      'q']) # quit
    
@dataclass
class Machine:
  memory: Memory
  threads: list[Thread]
  current_thread: Thread
  main_thread: Thread
  return_value: Value
  pause : bool = False # for debugger control

  # Run the machine on the given program.
  # Execution begins by calling the 'main' function.
  def run(self, decls):
      self.main_thread = Thread([], None, None, 0)
      self.current_thread = self.main_thread
      self.threads = [self.main_thread]
      self.push_frame()

      # Evaluate all of the function definitions.
      env = {}
      for d in decls:
        if isinstance(d, Function) and d.name == 'main':
          main = d
        d.declare(env, self.memory)
      for d in reversed(decls):
        self.schedule(d, env, return_mode='-no-return-mode-')
        
      old_debug = debug()
      set_debug(False)
      self.loop()
      set_debug(old_debug)

      # Call the 'main' function.
      self.threads = [self.main_thread]
      self.push_frame()
      loc = main.location
      call_main = Call(loc, Var(loc, 'main'), [])
      self.schedule(call_main, env, return_mode='-no-return-mode-')
      self.loop()

      # Cleanup by deleting the top-level environment.
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

      # Check for memory leaks.
      if self.memory.size() > 0:
          print('result:')
          print(self.return_value)
          if tracing_on():
              print('final memory:')
              print(self.memory)
          error(main.location, 'memory leak, memory size = '
                + str(self.memory.size()))
      return self.return_value

  def loop(self):
      self.pause = True
      while len(self.threads) > 0:
          t = random.randint(0, len(self.threads)-1)
          self.current_thread = self.threads[t]
          if tracing_on():
            print('thread = ' + str(id(self.current_thread)))
          # case current_thread is finished
          if len(self.current_thread.stack) == 0:
            if self.current_thread.num_children == 0:
              self.threads.remove(self.current_thread)
              if not self.current_thread.parent is None:
                  self.current_thread.parent.num_children -= 1
              if self.current_thread == self.main_thread:
                  self.return_value = self.current_thread.return_value
            continue
          # case current_thread has work to do
          frame = self.current_frame()
          if len(frame.todo) > 0:
            runner = self.current_runner()
            if tracing_on():
              print(error_header(runner.ast.location))
              print('stepping ' + repr(runner))
            if debug() and self.pause and not runner.ast.debug_skip():
              while True:
                print('> ' + str(runner.ast))
                debug_cmd = getch()
                if not (debug_cmd in debug_commands):
                  print(debug_cmd
                        + ' is not a valid debugger command, try one of\n'
                        + str(debug_commands))
                elif debug_cmd == 'q': # quit
                  exit(-1)
                elif debug_cmd == 'e':
                  self.print_env(runner.env, runner.ast.location)
                  continue
                elif debug_cmd == 'm':
                  print_dict(machine.memory.memory)
                  continue
                elif debug_cmd == 'f':
                  machine.pause = False
                  runner.pause_on_finish = True
                  break
                elif debug_cmd == 'c':
                  machine.pause = False
                  break
                elif debug_cmd == 'd':
                  machine.pause = False
                  machine.current_thread.pause_on_call = True
                  break
                elif debug_cmd == 'g':
                  log_graphviz('top', self.current_runner().env,
                               self.memory.memory)
                  continue
                elif debug_cmd == 'v':
                  set_verbose(not verbose())
                  continue
                else:
                  break
              set_debug_mode(debug_cmd)
            try:
              runner.ast.step(runner, self)
            except Exception as ex:
              if debug():
                print(ex)
                self.pause = True
                continue
              else:
                new_ex = Exception(str(ex) + '\nin evaluation of\n'
                                   + str(self.current_runner().ast))
                raise new_ex
            if tracing_on() and len(frame.todo) > 0:
              print('before log_graphviz, env:')
              print(self.current_runner().env)
              log_graphviz('top', self.current_runner().env, self.memory.memory)
              print(machine.memory)
              print()
            #machine.memory.compute_fractions()
            runner.state += 1
          else:
            self.current_thread.stack.pop()

  # Call schedule to queue the evaluation of an AST node.
  # Returns the new runner.
  def schedule(self, ast, env, context=ValueCtx(), return_mode=None):
      return_mode = self.current_runner().return_mode if return_mode is None \
                    else return_mode
      runner = NodeRunner(ast, 0, [], None, return_mode, context, env)
      self.current_frame().todo.append(runner)
      return runner

  # Call finish_expression to signal that the current expression
  # runner is finished and register the value it produced with the
  # previous runner.
  def finish_expression(self, result: Result, location):
      assert isinstance(result, Result)
      if self.current_runner().pause_on_finish:
          self.pause = True
          print('\t=> ' + str(result.value))
          print('\t\tin context ' + str(self.current_runner().context))
      elif debug() and (debug_mode() == 's' or debug_mode() == 'n'):
          print('\t=> ' + str(result.value))
          print('\t\tin context ' + str(self.current_runner().context))
      if tracing_on():
          print('finish_expression ' + str(result))
          print(self.memory)
      for res in self.current_runner().results:
          if res.temporary:
              # Catch a common mistake in the interpreter!
              if res.value is result.value:
                  error(location, "*** result is a temporary that's being deleted!")
              res.value.kill(machine.memory, location)
      self.current_frame().todo.pop()
      if len(self.current_frame().todo) > 0:
          self.current_runner().results.append(result)
      elif len(self.current_thread.stack) > 1:
          self.pop_frame(result.value)
      else:
          if tracing_on():
              print('finished thread ' + str(result))
          self.current_thread.return_value = result.value

  # Call finish_statement to signal that the current statement runner is done.
  # Propagates the return value if there is one.
  def finish_statement(self, location):
      if self.current_runner().pause_on_finish:
          self.pause = True
      val = self.current_runner().return_value
      if tracing_on():
          print('finish_statement ' + str(val))
          print('killing temporaries')
      for res in self.current_runner().results:
          if res.temporary:
              res.value.kill(machine.memory, location)
      self.current_frame().todo.pop()
      if len(self.current_frame().todo) > 0:
        self.current_runner().return_value = val
      elif len(self.current_thread.stack) > 1:
        self.pop_frame(val)
      else:
        self.return_value = val

  def finish_definition(self, location):
    if self.current_runner().pause_on_finish:
        self.pause = True
    for res in self.current_runner().results:
        if res.temporary:
            res.value.kill(machine.memory, location)
    self.current_frame().todo.pop()
        
  def push_frame(self):
      frame = Frame([])
      self.current_thread.stack.append(frame)

  def pop_frame(self, val : Value):
      self.current_thread.stack.pop()
      self.current_runner().return_value = val

  def current_frame(self):
      return self.current_thread.stack[-1]

  def current_runner(self):
      return self.current_frame().todo[-1]

  def spawn(self, exp: Exp, env):
      runner = NodeRunner(exp, 0, [], None,
                       self.current_runner().return_mode, # ??
                       ValueCtx(), env)
      frame = Frame([runner])
      self.current_thread.num_children += 1
      thread = Thread([frame], None, self.current_thread, 0)
      self.threads.append(thread)
      return thread

  def print_env(self, env, loc):
    for (k,ptr) in env.items():
      if ptr.get_address() is None:
        val = None
      else:
        val = machine.memory.raw_read(ptr.get_address(),
                                      ptr.get_ptr_path(), loc)
      print(str(k) + ':\t' + str(val) + '\t\t\t' + str(ptr))
    print()

# Command-line flags
flags = set(['trace', # Enable the tracing output. (i.e. "printf" debugging)
             'debug', # Run the debugger.
             'fail',  # The program is expected to fail at runtime.
             'static_fail']) # The program is expected to fail during type checking.

# Run the machine on the specified files, and process the command-line flags.
if __name__ == "__main__":
    # Set some global variables based on the command-line flags.
    if 'fail' in sys.argv:
      set_expect_fail(True)
    if 'static_fail' in sys.argv:
      set_expect_static_fail(True)
    if 'trace' in sys.argv:
      set_trace(True)
      set_verbose(True)
    if 'debug' in sys.argv:
      set_debug(True)
    else:
      set_debug(False)

    # Parse the program files.
    decls = []
    for filename in sys.argv[1:]:
      if not (filename in flags):
        set_filename(filename)
        file = open(filename, 'r')
        p = file.read()
        decls += parse(p, False)

    # Evaluate constant expressions.
    decls = const_eval_decls(decls, {})
    if tracing_on():
      print('**** after const_eval ****')
      for decl in decls:
          print(decl)
          print()
      print()

    # Type check the program.
    try:
      decls = type_check_program(decls)
      if tracing_on():
        print('**** finished type checking ****')
        for decl in decls:
          print(decl)
          print()
        print()

      # Run the program
      machine = Machine(Memory(), [], None, None, None)
      retval = machine.run(decls)
      
      if expect_fail():
          print("expected failure, but didn't, returned " + str(retval))
          exit(-1)
      else:
          if tracing_on() or debug():
              print('result: ' + str(retval.value))
          exit(int(retval.value))
    except StaticError as ex:
        if expect_static_fail():
            exit(0)
        else:
            print('Type checking error:')
            if tracing_on() or debug():
                raise ex
            else:
                print(str(ex))
                print()
                exit(-1)
    except Exception as ex:
        if expect_fail():
            exit(0)
        else:
            print('Runtime error:')
            if tracing_on() or debug():
                raise ex
            else:
                print(str(ex))
                print()
                exit(-1)


