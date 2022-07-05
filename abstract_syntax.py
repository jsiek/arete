from dataclasses import dataclass
from typing import List, Set, Dict, Tuple, Any

@dataclass
class Exp:
    pass

@dataclass
class Stmt:
    pass

@dataclass
class Pat:
    pass

# Parameters

@dataclass(frozen=True)
class Param:
    kind: str # read, write
    ident: str
    __match_args__ = ("kind", "ident")
    def __str__(self):
        return self.kind + " " + self.ident
    def __repr__(self):
        return str(self)

# Expressions

@dataclass
class Call(Exp):
    fun: Exp
    args: List[Exp]
    __match_args__ = ("fun", "args")
    def __str__(self):
        return str(self.fun) \
            + "(" + ", ".join([str(arg) for arg in self.args]) + ")"
    def __repr__(self):
        return str(self)

def op_str(op):
    if op == 'add':
        return '+'
    elif op == 'sub':
        return '-'
    elif op == 'neg':
        return '-'
    else:
        raise Exception('unhandled op ' + op)
    
@dataclass
class Prim(Exp):
    op: str
    args: List[Exp]
    __match_args__ = ("op", "args")
    def __str__(self):
        if len(self.args) == 1:
            return op_str(self.op) + str(self.args[0])
        elif len(self.args) == 2:
            return str(self.args[0]) + " " + op_str(self.op) + " " + \
                str(self.args[1])
        else:
            return self.op + \
                "(" + ", ".join([str(arg) for arg in self.args]) + ")"
    def __repr__(self):
        return str(self)

@dataclass
class New(Exp):
    init: Any
    __match_args__ = ("init",)
    def __str__(self):
        return "new " + str(self.init)
    def __repr__(self):
        return str(self)

@dataclass
class Deref(Exp):
    arg: Exp
    __match_args__ = ("arg",)
    def __str__(self):
        return "*" + str(self.arg)
    def __repr__(self):
        return str(self)
    
@dataclass
class Var(Exp):
    ident: str
    __match_args__ = ("ident",)
    def __str__(self):
        return self.ident
    def __repr__(self):
        return str(self)

@dataclass
class Int(Exp):
    value: int
    __match_args__ = ("value",)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self)

@dataclass
class Bool(Exp):
    value: bool
    __match_args__ = ("value",)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self)
    
@dataclass
class TupleExp(Exp):
    elts: List[Exp]
    __match_args__ = ("elts",)
    def __str__(self):
        return "⟨" + ", ".join([str(e) for e in self.elts]) + "⟩"
    def __repr__(self):
        return str(self)

@dataclass
class Index(Exp):
    arg: Exp
    index: Exp
    __match_args__ = ("arg", "index")
    def __str__(self):
        return str(self.arg) + "[" + str(self.index) + "]"
    def __repr__(self):
        return str(self)
    
@dataclass
class Lambda(Exp):
    params: List[Param]
    return_priv: str
    body: Stmt
    __match_args__ = ("params", "return_priv", "body")
    def __str__(self):
        return "fn " + ", ".join([str(p) for p in self.params]) \
            + " -> " + self.return_priv + " " \
            + "{ " + str(self.body) + " }"
    def __repr__(self):
        return str(self)

# Statements

@dataclass
class VarInit(Stmt):
    var: Param
    init: Exp
    rest: Stmt
    __match_args__ = ("var", "init", "rest")
    def __str__(self):
        return "var " + str(self.var) + " = " + str(self.init) + "; ..."
    def __repr__(self):
        return str(self)

@dataclass
class Write(Stmt):
    lhs: Exp
    rhs: Exp
    __match_args__ = ("lhs", "rhs")
    def __str__(self):
        return str(self.lhs) + " := " + str(self.rhs) + ";"
    def __repr__(self):
        return str(self)
    
@dataclass
class Delete(Stmt):
    arg: Exp
    __match_args__ = ("arg",)
    def __str__(self):
        return "delete " + str(self.arg) + ";"
    def __repr__(self):
        return str(self)
    
@dataclass
class Return(Stmt):
    exp: Exp
    __match_args__ = ("exp",)
    def __str__(self):
        return "return " + str(self.exp) + ";"
    def __repr__(self):
        return str(self)

@dataclass
class Expr(Stmt):
    exp: Exp
    __match_args__ = ("exp",)
    def __str__(self):
        return str(self.exp) + ";"
    def __repr__(self):
        return str(self)

@dataclass
class Pass(Stmt):
    def __str__(self):
        return ""
    def __repr__(self):
        return str(self)

@dataclass
class Seq(Stmt):
    first: Stmt
    rest: Stmt
    __match_args__ = ("first", "rest")
    def __str__(self):
        return str(self.first) + "..."
    def __repr__(self):
        return str(self)

@dataclass
class IfStmt(Stmt):
    cond: Exp
    thn: Stmt
    els: Stmt
    __match_args__ = ("cond", "thn", "els")
    def __str__(self):
        return "if " + str(self.cond) + "..."
    def __repr__(self):
        return str(self)
    
@dataclass
class Match(Stmt):
    arg: Exp
    cases: Any
    __match_args__ = ("arg", "cases")
    def __str__(self):
        return "match " + str(self.arg) + " " + "..."
    def __repr__(self):
        return str(self)

# Patterns

@dataclass
class VarPat(Pat):
    kind: str  # read, write
    ident: str
    __match_args__ = ("kind", "ident")
    def __str__(self):
        return self.kind + " " + self.ident
    def __repr__(self):
        return str(self)

@dataclass
class TuplePat(Pat):
    elts: List[Pat]
    __match_args__ = ("elts",)
    def __str__(self):
        return "⟨" + ", ".join([str(e) for e in self.elts]) + "⟩"
    def __repr__(self):
        return str(self)

@dataclass
class WildCard(Pat):
    def __str__(self):
        return "_"
    def __repr__(self):
        return str(self)
    
    
# Miscelaneous

@dataclass
class Initializer:
    kind: str # read, write
    arg: Exp
    __match_args__ = ("kind", "arg")
    def __str__(self):
        return self.kind + " " + str(self.arg)
    def __repr__(self):
        return str(self)
    
@dataclass
class Case:
    pat: Pat
    body: Stmt
    __match_args__ = ("pat", "body")
    def __str__(self):
        return "case " + str(self.pat) + ": " + str(self.body)
    def __repr__(self):
        return str(self)
