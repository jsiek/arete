
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

from typing import Any
import interp
from abstract_syntax import AST

@dataclass
class Action:
    ast: AST
    state: int
    env: dict[str,Value]
    result: Value
    
@dataclass
class Frame:
    todo: list[Action]
    
@dataclass
class Machine:
    memory: dict[int,Value]
    stack: list[Frame]

    def run(decls):
        pass

    def loop():
        while len(self.stack) > 0:
            frame = self.stack[0]
            if len(frame) > 0:
                action = frame[0]
                action.ast.step(action.state, action.env, self)
                action.state += 1
            else:
                self.stack.pop()
                
    # Call schedule to start the evaluation of an AST node. 
    def schedule(ast, env):
        action = Action(ast, 0, env)
        self.stack.append(action)
        return action

    # Calling finalize signals to the machine that the
    # current action is finished.
    def finalize(val):
        frame = self.stack[0]
        action = frame[0]
        action.result = val
        frame.pop()
