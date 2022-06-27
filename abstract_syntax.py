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
class Release(Exp):
    arg: Exp
    __match_args__ = ("arg",)

@dataclass
class Share(Exp):
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
    body: List[Stmt]
    __match_args__ = ("params", "body")

@dataclass
class Init(Stmt):
    var: str
    init: Exp
    __match_args__ = ("var", "init")

@dataclass
class Assign(Stmt):
    var: str
    rhs: Exp
    __match_args__ = ("var", "rhs")

@dataclass
class Write(Stmt):
    lhs: Exp
    rhs: Exp
    __match_args__ = ("lhs", "rhs")
    
@dataclass
class Borrow(Stmt):
    var: str
    init: Exp
    body: Stmt
    __match_args__ = ("var", "init", "body")

@dataclass
class Block(Stmt):
    body: List[Stmt]
    __match_args__ = ("body",)

@dataclass
class Return(Stmt):
    exp: Exp
    __match_args__ = ("exp",)

@dataclass
class Expr(Stmt):
    exp: Exp
    __match_args__ = ("exp",)
    
