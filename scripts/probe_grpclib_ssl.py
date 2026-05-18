import inspect
import grpclib.client
print(inspect.getsource(grpclib.client.Channel._get_default_ssl_context))
