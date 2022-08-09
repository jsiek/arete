from dataclasses import dataclass
from lark.tree import Meta
import numbers
from fractions import Fraction
from typing import Any, Optional
from ast_base import *

trace = False

def set_trace(b: bool):
  global trace
  trace = b

def tracing_on():
  return trace

# Context information:
#    1. do you want value or address of the expression? (i.e. rvalue/lvalue)
#       a) how much permission do you want? (give a percentage)
#    2. duplicate (normal) or no duplicate (for permission ops)?

@dataclass
class Context:
    duplicate: bool

# Want the value of the expression (not its address).
# If the value is a pointer, duplicate with the specified percentage
# of its permission.
# (rvalue)
@dataclass
class ValueCtx(Context):
  percentage : Fraction

# Want a copy of the address of the expression's result with
# the specified percentage of its permission.
# (lvalue)
@dataclass
class AddressCtx(Context):
  percentage : Fraction

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
            
def error(location, msg):
    raise Exception(error_header(location) + msg)

def warning(location, msg):
    header = '{file}:{line1}.{column1}-{line2}.{column2}: ' \
        .format(file=location.filename,
                line1=location.line, column1=location.column,
                line2=location.end_line, column2=location.end_column)
    print(header + 'warning: ' + msg)

def writable(frac):
    return frac == Fraction(1, 1)

def readable(frac):
    return Fraction(0, 1) < frac and frac < Fraction(1, 1)

def none(frac):
    return frac == Fraction(0, 1)
