from threading import Thread, Event
from enum import Enum
import logging
from functools import wraps


def action_valid_decorator_factory(state, protocol):
    """
    This decorator factory  is used to generate decorators which  verify that
    requested actions on a target, such as step(), stop(), read_register(), 
    write_register() and so on are actually executable.

    :param state: The required state of the Target
    :type state:  An entry of the Enum TargetStates
    :param protocol: The protocol required to execute the action.
    :type protocol: str
    """
    def decorator(func):
        @wraps(func)
        def check(self, *args, **kwargs):
            if getattr(self, protocol) == None:
                raise Exception(
                    "%s() requested but %s is undefined." %
                        (func.__name__, protocol))
            if self.state != state:
                raise Exception("%s() requested but Target is %s" %
                               (func.__name__, TargetStates(self.state).name))
            return func(self, *args, **kwargs)
        return check
    return decorator

        



class TargetStates(Enum):
    """
    A simple Enum for the different states a target can be in.
    """
    CREATED = 0x1
    INITIALIZED = 0x2
    STOPPED = 0x4
    RUNNING = 0x8
    SYNCHING = 0x10
    EXITED = 0x20

class Target(object):
    """The Target object is one of Avatars core concept, as Avatar orchestrate 
    different targets.
    While the generic target has no implementation, it provides an insight over 
    all the functions a Target MUST implement
    """


    def __init__(self, name, avatar):
        super(Target, self).__init__()
        self.state = TargetStates.CREATED

        self.name = name
        self.avatar = avatar
        self.status = {}
        self._arch = avatar.arch
        self._exec_protocol = None
        self._memory_protocol = None
        self._register_protocol = None
        self._signal_protocol = None
        self._monitor_protocol = None
        self._remote_memory_protocol = None

        self.state = TargetStates.CREATED
        self._no_state_update_pending = Event()
        
        self.log = logging.getLogger('%s.targets.%s' % (avatar.log.name, name))
        log_file = logging.FileHandler('%s/%s.log' % (avatar.output_directory, name))
        formatter = logging.Formatter('%(asctime)s | %(name)s.%(levelname)s | %(message)s')
        log_file.setFormatter(formatter)
        self.log.addHandler(log_file)


    def init(self):
        """
        Initializes the target to start the analyses
        """
        pass

    def shutdown(self):
        """
        Shutdowns the target
        """
        if self._exec_protocol:
            self._exec_protocol.shutdown()
            self._exec_protocol = None
        if self._memory_protocol:
            self._memory_protocol.shutdown()
            self._memory_protocol = None
        if self._register_protocol:
            self._register_protocol.shutdown()
            self._register_protocol = None
        if self._signal_protocol:
            self._signal_protocol.shutdown()
            self._signal_protocol = None
        if self._monitor_protocol:
            self._monitor_protocol.shutdown()
            self._monitor_protocol = None
        if self._remote_memory_protocol:
            self._remote_memory_protocol.shutdown()
            self._remote_memory_protocol = None

    @action_valid_decorator_factory(TargetStates.STOPPED, '_exec_protocol')
    def cont(self):
        """
        Continues the execution of the target
        :returns: True on success
        """
        self._no_state_update_pending.clear()
        return self._exec_protocol.cont()


    @action_valid_decorator_factory(TargetStates.RUNNING, '_exec_protocol')
    def stop(self):
        """
        Stops the execution of the target 
        """
        self._no_state_update_pending.clear()
        return self._exec_protocol.stop()


    @action_valid_decorator_factory(TargetStates.STOPPED, '_exec_protocol')
    def step(self):
        """
        Steps one instruction
        """
        self._no_state_update_pending.clear()
        return self._exec_protocol.step()


    @action_valid_decorator_factory(TargetStates.STOPPED, '_memory_protocol')
    def write_memory(self, address, size, value, num_words=1, raw=False):
        """
        Writing to memory of the target

        :param address:   The address from where the memory-write should 
                          start
        :param size:      The size of the memory write 
        :param value:     The actual value written to memory
        :type val:        int if num_words == 1 and raw == False
                          list if num_words > 1 and raw == False
                          str or byte if raw == True
        :param num_words: The amount of words to read
        :param raw:       Specifies whether to write in raw or word mode
        :returns:         True on success else False
        """
        return self._memory_protocol.write_memory(address, size, value, 
                                                  num_words, raw)


    @action_valid_decorator_factory(TargetStates.STOPPED, '_memory_protocol')
    def read_memory(self, address, size, words=1, raw=False):
        """
        Reading from memory of the target

        :param address:     The address to read from 
        :param size:        The size of a read word
        :param words:       The amount of words to read (default: 1)
        :param raw:         Whether the read memory is returned unprocessed
        :return:          The read memory
        """
        return self._memory_protocol.read_memory(address, size, words, raw)


    @action_valid_decorator_factory(TargetStates.STOPPED, '_register_protocol')
    def write_register(self, register, value):
        """
        Writing a register to the target

        :param register:     The name of the register
        :param value:        The actual value written to the register
        """
        return self._register_protocol.write_register(register, value)

    @action_valid_decorator_factory(TargetStates.STOPPED, '_register_protocol')
    def read_register(self, register):
        """
        Reading a register from the target

        :param register:     The name of the register
        :return:             The actual value read from the register
        """
        return self._register_protocol.read_register(register)

    @action_valid_decorator_factory(TargetStates.STOPPED, '_exec_protocol')
    def set_breakpoint(self, line, hardware=False, temporary=False, regex=False,
                       condition=None, ignore_count=0, thread=0):
        """Inserts a breakpoint

        :param bool hardware: Hardware breakpoint
        :param bool tempory:  Tempory breakpoint
        :param str regex:     If set, inserts breakpoints matching the regex
        :param str condition: If set, inserts a breakpoint with the condition
        :param int ignore_count: Amount of times the bp should be ignored
        :param int thread:    Threadno in which this breakpoints should be added
        """
        return self._exec_protocol.set_breakpoint(line, hardware=hardware,
                                                  temporary=temporary, 
                                                  regex=regex,
                                                  condition=condition, 
                                                  ignore_count=ignore_count,
                                                  thread=thread)

    @action_valid_decorator_factory(TargetStates.STOPPED, '_exec_protocol')
    def set_watchpoint(self, variable, write=True, read=False):
        """Inserts a watchpoint

        :param      variable: The name of a variable or an address to watch
        :param bool write:    Write watchpoint
        :param bool read:     Read watchpoint
        """
        return self._exec_protocol.set_watchpoint(variable,
                                                  write=write,
                                                  read=read)

    @action_valid_decorator_factory(TargetStates.STOPPED, '_exec_protocol')
    def remove_breakpoint(self, bkptno):
        """Deletes a breakpoint"""
        return self._exec_protocol.remove_breakpoint(bkptno)


    def update_state(self, state):
        self.log.info("State changed to to %s" % TargetStates(state))
        self.state = state
        self._no_state_update_pending.set()


    def wait(self):
        while True:
            self._no_state_update_pending.wait(.1)
            if self.state == TargetStates.STOPPED and \
               self._no_state_update_pending.is_set():
                break

    def get_status(self):
        """
        Returns useful information about the target as a dict.
        """
        self.status['state'] = self.state
        return self.status 


    ###generic aliases###
    wr = write_register
    rr = read_register
    rm = read_memory
    wm = write_memory
