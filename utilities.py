from dataclasses import dataclass
from lark.tree import Meta
import numbers
from fractions import Fraction
from typing import Any, Optional
from ast_base import *

# flag for tracing

trace = False

def set_trace(b: bool):
  global trace
  trace = b

def tracing_on():
  return trace

# flag for debugging

debug_flag = False

def debug():
  return debug_flag

def set_debug(v):
  global debug_flag
  debug_flag = v

# debug mode

debug_cmd = 's'

def debug_mode():
  return debug_cmd

def set_debug_mode(cmd):
  global debug_cmd
  debug_cmd = cmd


# flag for verbose

verbose_flag = False

def verbose():
  return verbose_flag

def set_verbose(v):
  global verbose_flag
  verbose_flag = v

# interpreting primitives

interp_prim = {}

def set_primitive_interp(op, fun):
  interp_prim[op] = fun

def get_primitive_interp(op):
  return interp_prim[op]

# type checking primitives

type_check_prim = {}

def set_primitive_type_check(op, fun):
  type_check_prim[op] = fun

def get_primitive_type_check(op):
  if not op in type_check_prim.keys():
    raise Exception('unrecognized primitive operation ' + op)
  return type_check_prim[op]
  
# Context information:
# do you want value or address of the expression? (i.e. rvalue/lvalue)

@dataclass
class Context:
  duplicate: bool = True # false for arguments of Transfer

# Want the value of the expression (not its address).
# (rvalue)
@dataclass
class ValueCtx(Context):
  pass

# Want the address of the expression's result.
# (lvalue)
@dataclass
class AddressCtx(Context):
  pass

def priv_to_percent(priv):
  if priv == 'write':
    return Fraction(1,1)
  elif priv == 'read':
    return Fraction(1,2)
  elif priv == 'none':
    return Fraction(0,1)
  else:
    raise Exception('in priv_to_percent, unrecognized ' + priv)

def error_header(location):
  # seeing a strange error where some Meta objects don't have a line member.
  if hasattr(location, 'line'):
    return '{file}:{line1}.{column1}-{line2}.{column2}: ' \
        .format(file=location.filename,
                line1=location.line, column1=location.column,
                line2=location.end_line, column2=location.end_column)
            
def warning(location, msg):
    header = '{file}:{line1}.{column1}-{line2}.{column2}: ' \
        .format(file=location.filename,
                line1=location.line, column1=location.column,
                line2=location.end_line, column2=location.end_column)
    print(header + 'warning: ' + msg)

def error(location, msg):
  raise Exception(error_header(location) + msg)
      
def writable(frac):
    return frac == Fraction(1, 1)

def readable(frac):
    return (Fraction(0, 1) < frac)

def none(frac):
    return frac == Fraction(0, 1)

def getch():
    import termios
    import sys, tty
    def _getch():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch
    return _getch()  

def print_dict(dict):
  for (k,v) in dict.items():
    print(str(k) + ': ' + str(v))
  print()

