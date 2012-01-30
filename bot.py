'''
This is a base for an IRC bot.
'''

import connect

class Bot(object):
    '''
    An IRC bot interface.
    '''
    def __init__(self, config, ident):
        '''
        @config must be a class that presents a particular interface.
        TODO: Describe the @config interface
        '''
        self.config = config
        self.ident = ident()
        self.conn = connect.IRCConn(self)
        self.cmds = config(self)
        self.conn.connect()
        self.conn.mainloop()
    
    def handle_privmsg(self, tokens, sender):
        chan = tokens.pop(0)
        tokens[0] = tokens[0].strip(':')
        if tokens[0] == self.ident.nick:
            tokens.pop(0)
            is_to_me = True
        else:
            is_to_me = False

        nick, host = sender.split('!')        
        if chan == self.ident.nick:
            chan = nick
        data = {'channel': chan, 'sender': sender, 'is_to_me': is_to_me,
                'nick': nick, 'host': host}
        
        cmd = tokens[0]
        try:
            args = tokens[1:]
        except IndexError:
            args = []
        
        if is_to_me and (cmd in self.cmds.addr_funcs):
            self.cmds.addr_funcs[cmd](args, data)
        elif cmd in self.cmds.unaddr_funcs:
            self.cmds.unaddr_funcs[cmd](args, data)
        else:
            for func in self.cmds.all_privmsg_funcs:
                func(tokens, data)
        
    def handle_other_join(self, tokens, joiner):
        chan = tokens.pop()
        nick, host = joiner.split('!')
        data = {'channel': chan, 'joiner': joiner, 'nick': nick, 'host': host}
        for func in self.cmds.other_join_funcs:
            func(data)
