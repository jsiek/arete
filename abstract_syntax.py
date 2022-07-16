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
class Decl(AST):
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
    def free_vars(self):
        percent_fv = set() if isinstance(self.percentage, str) \
            else self.percentage.free_vars()
        return percent_fv | self.arg.free_vars()
    
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
    def free_vars(self):
        return self.fun.free_vars() \
            | set().union(*[arg.free_vars() for arg in self.args])

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
    def free_vars(self):
        return set().union(*[arg.free_vars() for arg in self.args])

@dataclass
class Member(Exp):
    arg: Exp
    field: str
    __match_args__ = ("arg", "field")
    def __str__(self):
        return str(self.arg) + "." + self.field
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    
@dataclass
class New(Exp):
    inits: List[Initializer]
    __match_args__ = ("inits",)
    def __str__(self):
        return "new " + ", ".join([str(e) for e in self.inits])
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set().union(*[init.free_vars() for init in self.inits])

@dataclass
class Array(Exp):
    size: Exp
    arg: Exp
    __match_args__ = ("size","arg")
    def __str__(self):
        return "new " + "[" + str(self.size) + "]" + str(self.arg)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.size.free_vars() | self.arg.free_vars()
    
@dataclass
class Var(Exp):
    ident: str
    __match_args__ = ("ident",)
    def __str__(self):
        return self.ident
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set([self.ident])

@dataclass
class Int(Exp):
    value: int
    __match_args__ = ("value",)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set()

@dataclass
class Frac(Exp):
    value: Fraction
    __match_args__ = ("value",)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set()
    
@dataclass
class Bool(Exp):
    value: bool
    __match_args__ = ("value",)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set()
    
@dataclass
class Index(Exp):
    arg: Exp
    index: Exp
    __match_args__ = ("arg", "index")
    def __str__(self):
        return str(self.arg) + "[" + str(self.index) + "]"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars() | self.index.free_vars()
    
@dataclass
class Lambda(Exp):
    params: List[Param]
    body: Stmt
    __match_args__ = ("params", "body")
    def __str__(self):
        return "function " \
            + "(" + ", ".join([str(p) for p in self.params]) + ")" \
            + " { " + str(self.body) + " }"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.body.free_vars() - set([p.ident for p in self.params])
    
@dataclass
class IfExp(Exp):
    cond: Exp
    thn: Exp
    els: Exp
    __match_args__ = ("cond", "thn", "els")
    def __str__(self):
        return "(" + str(self.cond) + "?" + str(self.thn) \
            + " : " + str(self.els) + ")"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.cond.free_vars() | self.thn.free_vars() \
            | self.els.free_vars()
    
@dataclass
class Let(Exp):
    var: Param
    init: Initializer
    body: Exp
    __match_args__ = ("var", "init", "body")
    def __str__(self):
        return "var " + str(self.var) + " = " + str(self.init) + ";\n" \
            + str(self.body)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.init.free_vars() | \
            (self.body.free_vars() - set([self.var.ident]))

# Statements

@dataclass
class Seq(Stmt):
    first: Stmt
    rest: Stmt
    __match_args__ = ("first", "rest")
    def __str__(self):
        return str(self.first) + "\n" + str(self.rest)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.first.free_vars() | self.rest.free_vars()

@dataclass
class VarInit(Exp):
    var: Param
    init: Initializer
    body: Stmt
    __match_args__ = ("var", "init", "body")
    def __str__(self):
        return "var " + str(self.var) + " = " + str(self.init) + ";\n" \
            + str(self.body)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.init.free_vars() \
            | (self.body.free_vars() - set([self.var.ident]))

@dataclass
class Return(Stmt):
    arg: Exp
    __match_args__ = ("arg",)
    def __str__(self):
        return "return " + str(self.arg) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    
@dataclass
class Write(Stmt):
    lhs: Exp
    rhs: Exp
    __match_args__ = ("lhs", "rhs")
    def __str__(self):
        return str(self.lhs) + " = " + str(self.rhs) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.lhs.free_vars() | self.rhs.free_vars()

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
    def free_vars(self):
        return self.lhs.free_vars() | self.percent.free_vars() \
            | self.rhs.free_vars()
    
@dataclass
class Delete(Stmt):
    arg: Exp
    __match_args__ = ("arg",)
    def __str__(self):
        return "delete " + str(self.arg) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    
@dataclass
class Expr(Stmt):
    exp: Exp
    __match_args__ = ("exp",)
    def __str__(self):
        return str(self.exp) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.exp.free_vars()

@dataclass
class Assert(Stmt):
    exp: Exp
    __match_args__ = ("exp",)
    def __str__(self):
        return "assert " + str(self.exp) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.exp.free_vars()

@dataclass
class IfStmt(Stmt):
    cond: Exp
    thn: Stmt
    els: Stmt
    __match_args__ = ("cond", "thn", "els")
    def __str__(self):
        return "if " + "(" + str(self.cond) + ")\n" + str(self.thn) \
            + "else " + str(self.els)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.cond.free_vars() | self.thn.free_vars() \
            | self.els.free_vars()

@dataclass
class While(Stmt):
    cond: Exp
    body: Stmt
    __match_args__ = ("cond", "body")
    def __str__(self):
        return "while " + "(" + str(self.cond) + ")\n" + str(self.body) 
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.cond.free_vars() | self.body.free_vars()
    
@dataclass
class Pass(Stmt):
    def __str__(self):
        return "pass"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set()

@dataclass
class Block(Stmt):
    body: Exp
    __match_args__ = ("body",)
    def __str__(self):
        return "{\n" + str(self.body) + "\n}\n"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.body.free_vars()
    
# Declarations
    
@dataclass
class Global(Exp):
    name: str
    rhs: Exp
    __match_args__ = ("name", "rhs")
    def __str__(self):
        return "var " + str(self.name) + " = " + str(self.rhs) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return init.free_vars()
    def local_vars(self):
        return set([var.ident])
    
@dataclass
class Function(Decl):
    name: str
    params: List[Param]
    body: Exp
    __match_args__ = ("name", "params", "body")
    def __str__(self):
        return "function " + self.name \
            + "(" + ", ".join([str(p) for p in self.params]) + ")" \
            + " { " + str(self.body) + " }"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return body.free_vars() - set([p.ident for p in self.params])

@dataclass
class ModuleDecl(Decl):
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
