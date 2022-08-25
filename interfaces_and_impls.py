#
# This file defines the language features for constrained generics in Arete,
# which includes
# * interface definitions,
# * impl definitions, 
# * impl requirements.

# Use Module values for witness tables?

@dataclass
class Interface(Decl):
  name: str
  params: list[str]
  members: dict[Type]

  def __str__(self):
    return 'interface ' + self.name + '(' + ', '.join(self.params) + ')' + ' {\n'
      + '\n'.join(x + ': ' + str(t) for x,t in self.members.items())
    
  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    pass
  
  def step(self, runner, machine):
    pass

  def type_check(self, env):
    pass

@dataclass
class Impl(Decl):
  name: str
  args: list[Type]

  def __str__(self):
    return 'impl ' + self.name + '(' + ', '.join(str(self.args)) + ');'
    
  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    pass
  
  def step(self, runner, machine):
    pass

  def type_check(self, env):
    pass
  
@dataclass
class ImplReq(AST):
  name: str
  args: list[Type]

  def __str__(self):
    return self.name + '(' + ', '.join(str(self.args)) + ');'
    
  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    pass
  
  def step(self, runner, machine):
    pass

  def type_check(self, env):
    pass
  
