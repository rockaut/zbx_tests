import sys

# attempt to import zabbix runtime if running embedded
try:
  import zabbix_runtime
except ImportError:
  zabbix_runtime = None

__version__             = "1.0.0"

__python_version_string = "Python %i.%i.%i-%s" % sys.version_info[:4]

__modules               = []

__items                 = []

__routes                = {}

zabbix_module_path      = "/usr/lib/zabbix/modules/python%i" % sys.version_info[:1]

item_timeout            = 0

# log levels from log.h
LOG_LEVEL_CRIT          = 1
LOG_LEVEL_ERR           = 2
LOG_LEVEL_WARNING       = 3
LOG_LEVEL_DEBUG         = 4
LOG_LEVEL_TRACE         = 5
LOG_LEVEL_INFORMATION   = 127

def log(lvl, msg):
  if zabbix_runtime:
    zabbix_runtime.log(lvl, msg)

  elif lvl == LOG_LEVEL_INFORMATION:
    print(msg)

  elif lvl <= LOG_LEVEL_WARNING:
    sys.stderr.write(msg + "\n")

def info(msg):
  log(LOG_LEVEL_INFORMATION, msg)

def trace(msg):
  log(LOG_LEVEL_TRACE, msg)

def debug(msg):
  log(LOG_LEVEL_DEBUG, msg)

def warning(msg):
  log(LOG_LEVEL_WARNING, msg)

def error(msg):
  log(LOG_LEVEL_ERR, msg)

def critical(msg):
  log(LOG_LEVEL_CRIT, msg)

class TimeoutError(Exception):
  """
  TimeoutError should be raised by any agent item handler whose execution
  exceeds item_timeout seconds
  """

  def __str__(self):
    return 'Operation timed out'

class AgentRequest(object):
  key    = None
  params = []

  def __init__(self, key, params):
    self.key = key
    self.params = params

  def __str__(self):
    return "{0}[{1}]".format(self.key, ','.join(self.params))

class AgentItem(object):
  key        = None
  flags      = 0
  test_param = None
  fn         = None

  def __init__(self, key, flags = 0, fn = None, test_param = None):
    if not key:
      raise ValueError("key not given in agent item")

    if not fn:
      raise ValueError("fn not given in agent item")

    # join test_param if list or tuple given
    if test_param:        
      try:
        for i, v in enumerate(test_param):
          test_param[i] = str(v)

        test_param = ','.join(test_param)

      except TypeError:
        test_param = str(test_param)

    self.key = key
    self.flags = flags
    self.test_param = test_param
    self.fn = fn

  def __str__(self):
    return self.key

def route(request):
  """
  Route a request from the Zabbix agent to the Python function associated with
  the request key.
  """

  debug("routing python request: %s" % request)

  try:
    return __routes[request.key](request)

  except KeyError:
    raise ValueError("no function registered for agent item " + request.key)

def version(request):
  """Agent item python.version returns the runtime version string"""
  
  return __python_version_string

def macro_name(key):
  """Converts a string into a Zabbix LLD macro"""

  from re import sub
  macro = key.upper()                     # uppercase
  macro = sub(r'[\s_-]+', '_', macro)     # replace whitespace with underscore
  macro = sub(r'[^a-zA-Z_]+', '', macro)  # strip illegal chars
  macro = sub(r'[_]+', '_', macro)        # reduce duplicates
  macro = ('{#' + macro + '}')            # encapsulate in {#}

  return macro

def discovery(data):
  """Converts a Python dict into a Zabbix LLD JSON string"""

  from json import JSONEncoder
  lld_data = { 'data': [] }
  for item in data:
    lld_item = {}
    for key, val in item.items():
      if val:
        lld_item[macro_name(key)] = str(val)

    if lld_item:
      lld_data['data'].append(lld_item)

  return JSONEncoder().encode(lld_data)

def register_item(item):
  """Registers an AgentItem for use in the parent Zabbix process"""

  debug("registering item %s" % item.key)
  __items.append(item)
  __routes[item.key] = item.fn

  return item

def register_module_items(mod):
  """
  Retrieves a list of AgentItems by calling zbx_module_item_list in the given
  module, if it exists. Each item is then registered for use in the parent
  Zabbix process.
  """
  if isinstance(mod, str):
    mod = sys.modules[mod]

  debug("calling %s.zbx_module_item_list" % mod.__name__)
  try:
    newitems = mod.zbx_module_item_list()

    try:
      for item in newitems:
        register_item(item)
    except TypeError:
      # newitems is probably a single item
      register_item(newitems)

  except AttributeError:
    # module does not define zbx_module_item_list
    newitems = []

  return newitems

def register_module(mod):
  """
  Initializes the given module by calling its zbx_module_init function, if it
  exists. Any AgentItems in the module are then registered via
  register_module_items.
  """

  # import module
  debug("registering module: %s" % mod)
  if isinstance(mod, str):
      mod = __import__(mod)

  __modules.append(mod)

  # init module
  try:
    debug("calling %s.zbx_module_init" % mod.__name__)
    mod.zbx_module_init()
  except AttributeError:
    pass

  # register items
  register_module_items(mod)

  return mod

def zbx_module_init():
  """
  This function is called by the Zabbix runtime when the module is first loaded.
  It initializes and registers builtin AgentItems and all modules from the
  configured zabbix_module_path.
  """

  import glob
  import os.path

  # ensure module path is in search path
  sys.path.insert(0, zabbix_module_path)

  # register builtin items
  register_item(AgentItem("python.version", fn = version))

  # init list of modules to register
  mod_names = []

  # register installed packages
  for path in glob.glob(zabbix_module_path + "/*/__init__.py"):
    mod_name = os.path.basename(os.path.split(path)[0])

    if mod_name != __name__:
      mod_names.append(mod_name)
      register_module(mod_name)

  # register installed modules
  for path in glob.glob(zabbix_module_path + "/*.py"):
    filename = os.path.basename(path)
    mod_name = filename[0:len(filename) - 3]

    if mod_name != __name__:
      mod_names.append(filename)
      register_module(mod_name)

  # log loaded modules
  if mod_names:
    info("loaded python modules: %s" % ", ".join(mod_names))

def zbx_module_item_list():
  """
  This function is called by the Zabbix runtime and returns all registered
  AgentItems for use in the parent Zabbix process.
  """
  
  return __items
