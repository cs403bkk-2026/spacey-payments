# Request log to stdout. %(U)s is the path without the query string, and the
# referer is left out, so nothing sensitive in a URL is logged.
accesslog = "-"
access_log_format = '%(h)s %(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(M)sms "%(a)s"'
