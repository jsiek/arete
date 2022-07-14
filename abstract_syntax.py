from dataclasses import dataclass
from typing import List, Set, Dict, Tuple, Any
from lark.tree import Meta
from fractions import Fraction

@dataclass
class AST:
    location: Meta

@dataclass
class Exp(AST):
    pass

@dataclass
class Stmt(AST):
    pass

@dataclass
class Pat(AST):
    pass

# Parameters

@dataclass(frozen=True)
class Param:
    location: Meta
    kind: str # read, write
    ident: str
    __match_args__ = ("kind", "ident")
    def __str__(self):
        return self.kind + " " + self.ident
    def __repr__(self):
        return str(self)

# Miscelaneous

@dataclass
class Initializer:
    location: Meta
    percentage: Exp
    arg: Exp
    __match_args__ = ("location", "percentage", "arg")
    def __str__(self):
        return str(self.percentage) + " of " + str(self.arg)
    def __repr__(self):
        return str(self)
    
@dataclass
class Case:
    location: Meta
    pat: Pat
    body: Stmt
    __match_args__ = ("pat", "body")
    def __str__(self):
        return "case " + str(self.pat) + ": " + str(self.body)
    def __repr__(self):
        return str(self)

# Expressions

@dataclass
class Call(Exp):
    fun: Exp
    args: List[Initializer]
    __match_args__ = ("fun", "args")
    def __str__(self):
        return str(self.fun) \
            + "(" + ", ".join([str(arg) for arg in self.args]) + ")"
    def __repr__(self):
        return str(self)

@dataclass
class Prim(Exp):
    op: str
    args: List[Exp]
    __match_args__ = ("op", "args")
    def __str__(self):
        return self.op + \
            "(" + ", ".join([str(arg) for arg in self.args]) + ")"
        
    def __repr__(self):
        return str(self)

@dataclass
class Member(Exp):
    arg: Exp
    field: str
    __match_args__ = ("arg", "field")
    def __str__(self):
        return str(self.arg) + "." + self.field
    def __repr__(self):
        return str(self)
    
@dataclass
class New(Exp):
    inits: List[Exp]
    __match_args__ = ("inits",)
    def __str__(self):
        return "new " + ", ".join([str(e) for e in self.inits])
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
class Frac(Exp):
    value: Fraction
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
class Block(Stmt):
    body: Stmt
    __match_args__ = ("body",)
    def __str__(self):
        return "{ " + str(self.body) + " }"
    def __repr__(self):
        return str(self)
    
@dataclass
class VarInit(Stmt):
    var: Param
    init: Initializer
    __match_args__ = ("var", "init")
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
        return str(self.lhs) + " = " + str(self.rhs) + ";"
    def __repr__(self):
        return str(self)

@dataclass
class Transfer(Stmt):
    lhs: Exp
    percent: Exp
    rhs: Exp
    __match_args__ = ("lhs", "percent", "rhs")
    def __str__(self):
        return str(self.lhs) + " <= " + str(self.percent) + " of " \
            + str(self.rhs) + ";"
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

@dataclass
class Assert(Stmt):
    exp: Exp
    __match_args__ = ("exp",)
    def __str__(self):
        return "assert " + str(self.exp) + ";"
    def __repr__(self):
        return str(self)

@dataclass
class ModuleDecl(Stmt):
    name: str
    exports: List[str]
    body: Stmt
    __match_args__ = ("name", "exports", "body")
    def __str__(self):
        return 'module ' + self.name + '\n'\
            + '  exports ' + ", ".join(ex for ex in self.exports) + ' {\n' \
            + str(self.body) + '\n}\n'
    def __repr__(self):
        return str(self)
    
# Patterns

@dataclass
class ParamPat(Pat):
    param: Param
    __match_args__ = ("param",)
    def __str__(self):
        return str(self.param)
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
    
    
