'''
This is the core connection manager.
'''

from socket import socket, AF_INET, SOCK_STREAM

class IRCConn(object):
    
    '''
    This class handles the connection with the IRC server.
    It connects and sends and receives messages.
    '''
    
    def __init__(self, handler):
        self.handler = handler
        i = handler.ident
        self.ident = i.ident
        self.serv = i.serv
        self.host = i.host
        self.name = i.name
        self.nick = i.nick
        self.join_first = i.joins
        self.port = 6667
    
    def connect(self):
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self._send('USER {} {} {} :{}'.format(self.ident, self.host, self.serv, self.name))
        self._send('NICK {}'.format(self.nick))
        # wait until we have received the MOTD in full before proceeding

    def on_connect(self):
        '''
        Called once we have connected to and identified with the server.
        Mainly joins the channels that we want to join at the start.
        '''
        for chan in self.join_first:
            self.join(chan)
    
    def join(self, chan):
        self._send('JOIN {}'.format(chan))
    
    def leave(self, msg, chan):
        self._send('PART {} :{}'.format(chan, msg))
    
    def _send(self, msg):
        '''
        Send something (anything) to the IRC server.
        '''
        print('sending: {}\r\n'.format(msg))
        self.sock.send('{}\r\n'.format(msg).encode())
    
    def say(self, msg, chan, to=None):
        '''
        Say @msg on @chan.
        '''
        prefix = '' if to is None else '{}: '.format(to)
        for line in msg.splitlines():
            self._send('PRIVMSG {} :{}{}'.format(chan, prefix, line))
    
    def ident(self, pswd):
        self.say('identify {}'.format(pswd), 'NickServ')
    
    def describe(self, msg, chan):
        self.say('\x01ACTION %s\x01' % msg, chan)
    
    def pong(self, trail):
        self._send('PONG {}'.format(trail))
    
    def receive(self):
        '''
        Read from the socket until we reach the end of an IRC message.
        Attempt to decode the message and return it.
        Call handle_encoding_error() if unsuccessful.
        '''
        buf = []
        while True:
            nxt_ch = None
            ch = self.sock.recv(1)
            if ch == b'\r':
                nxt_ch = self.sock.recv(1)
                if nxt_ch == b'\n':
                    try:
                        line = b''.join(buf).decode()
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        self.handle_encoding_error()
                        return ''
                    print('received: {}'.format(line))
                    return line
            buf.append(ch)
            if nxt_ch:
                buf.append(nxt_ch)
            
        if not line.strip():
            return None
        else:
            try:
                parsable = line.strip(b'\r\n').decode()
                print('received: {}'.format(parsable))
                return parsable
            except (UnicodeEncodeError, UnicodeDecodeError):
                self.handle_encoding_error()
    
    def parse(self, line):
        if not line:
            # empty line; this should throw up an error.
            return
        line = line.strip('\r\n')
        tokens = line.split(' ')
        if tokens[0].startswith(':'):
            prefix = tokens.pop(0)[1:].strip(':')
        else:
            prefix = ''
        
        cmd = tokens.pop(0)
        if cmd == '433':    # nick already in use
            self.nick += '_'
            self._send('NICK {}'.format(self.nick))
        elif cmd == '376':    # end of MOTD
            self.on_connect()
        elif cmd == '422':    # No MOTD file
            self.on_connect()
        elif cmd == 'PING':
            self.pong(' '.join(tokens))
        elif cmd == 'ERROR':
            self.handle_error(tokens)
        elif cmd == 'JOIN':
            if prefix.split('!')[0] != self.nick:
                self.handler.handle_other_join(tokens, prefix)
        elif cmd == 'PRIVMSG':
            self.handler.handle_privmsg(tokens, prefix)
    
    def mainloop(self):
        '''
        The mainloop.
        '''
        while True:
            line = self.receive()
            self.parse(line)

    def handle_encoding_error(self):
        print('encoding error encountered.')
    
    def handle_error(self, tokens):
        print('error. tokens: {}'.format(tokens))
        self.connect()
