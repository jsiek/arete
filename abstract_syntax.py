from dataclasses import dataclass
from typing import List, Set, Dict, Tuple, Any

@dataclass
class Exp:
    pass

@dataclass
class Stmt:
    pass

@dataclass
class Call(Exp):
    fun: Exp
    args: List[Exp]
    __match_args__ = ("fun", "args")

@dataclass
class Prim(Exp):
    op: str
    args: List[Exp]
    __match_args__ = ("op", "args")

@dataclass
class New(Exp):
    arg: Exp
    __match_args__ = ("arg",)

@dataclass
class Deref(Exp):
    arg: Exp
    __match_args__ = ("arg",)
    
@dataclass
class Var(Exp):
    ident: str
    __match_args__ = ("ident",)

@dataclass
class Int(Exp):
    value: int
    __match_args__ = ("value",)

@dataclass
class Lambda(Exp):
    params: List[Any]
    body: Stmt
    __match_args__ = ("params", "body")

@dataclass
class Init(Stmt):
    kind: str
    var: str
    init: Exp
    rest: Stmt
    __match_args__ = ("kind", "var", "init", "rest")

@dataclass
class Write(Stmt):
    lhs: Exp
    rhs: Exp
    rest: Stmt
    __match_args__ = ("lhs", "rhs", "rest")
    
@dataclass
class Return(Stmt):
    exp: Exp
    __match_args__ = ("exp",)

@dataclass
class Expr(Stmt):
    exp: Exp
    rest: Stmt
    __match_args__ = ("exp", "rest")
    
@dataclass(frozen=True)
class Param:
    kind: str # share, take, borrow
    ident: str
    __match_args__ = ("kind", "ident")
