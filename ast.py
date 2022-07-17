from dataclasses import dataclass

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
