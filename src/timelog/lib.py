import copy
import fileinput
import UserDict
from re import compile
from django.conf import settings

from texttable import Texttable
from progressbar import ProgressBar, Percentage, Bar

from django.core.urlresolvers import resolve, Resolver404

PATTERN = r"""^([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9:]{8},[0-9]{3}) (GET|POST|PUT|DELETE|HEAD|OPTIONS|TRACE|CONNECT|PATCH) "(.*)" \((.*)\) (.*?) \((\d+)q, (.*?)\)"""

CACHED_VIEWS = {}

IGNORE_PATHS = getattr(settings, 'TIMELOG_IGNORE_URIS', ())

def count_lines_in(filename):
    "Count lines in a file"
    f = open(filename)                  
    lines = 0
    buf_size = 1024 * 1024
    read_f = f.read # loop optimization
    
    buf = read_f(buf_size)
    while buf:
        lines += buf.count('\n')
        buf = read_f(buf_size)
    
    return lines

def view_name_from(path):
    "Resolve a path to the full python module name of the related view function"
    try:
        return CACHED_VIEWS[path]
        
    except KeyError:
        view = resolve(path)
        module = path
        name = ''
        if hasattr(view.func, '__module__'):
            module = resolve(path).func.__module__
        if hasattr(view.func, '__name__'):
            name = resolve(path).func.__name__
        
        view =  "%s.%s" % (module, name)
        CACHED_VIEWS[path] = view
        return view

def add_stats_to(raw_data):
    data = {}
    for item in raw_data:
        data[item] = copy.deepcopy(raw_data[item])

        data[item]['mean'] = round(sum(data[item]['times'])/data[item]['count'], 3)
        data[item]['mean_sql'] = round(sum(data[item]['sql'])/data[item]['count'], 3)
        data[item]['mean_sqltime'] = round(sum(data[item]['sqltime'])/data[item]['count'], 3)
        
        sdsq = sum([(i - data[item]['mean']) ** 2 for i in data[item]['times']])
        try:
            data[item]['stdev'] = '%.2f' % ((sdsq / (len(data[item]['times']) - 1)) ** .5)
        except ZeroDivisionError:
            data[item]['stdev'] = '0.00'

        data[item]['minimum'] = "%.2f" % min(data[item]['times'])
        data[item]['maximum'] = "%.2f" % max(data[item]['times'])

    return data

def generate_table_from(data):
    "Output a nicely formatted ascii table"
    table = Texttable(max_width=120)
    table.add_row(["view", "method", "status", "count", "minimum", "maximum", "mean", "stdev", "queries", "querytime"]) 
    table.set_cols_align(["l", "l", "l", "r", "r", "r", "r", "r", "r", "r"])

    for item in sorted(data):
        table.add_row([data[item]['view'],
                       data[item]['method'],
                       data[item]['status'],
                       data[item]['count'],
                       data[item]['minimum'],
                       data[item]['maximum'],
                       '%.3f' % data[item]['mean'],
                       data[item]['stdev'],
                       data[item]['mean_sql'],
                       data[item]['mean_sqltime']])

    return table.draw()

def generate_csv_from(data):
    output = '"view","method","status","count","minimum","maximum","mean","stdev","queries","querytime"\n'
    for item in sorted(data):
        output += '"{0}","{1}","{2}","{3}","{4}","{5}","{6}","{7}","{8}","{9}"\n'.format(data[item]['view'],
                                                                                         data[item]['method'],
                                                                                         data[item]['status'],
                                                                                         data[item]['count'],
                                                                                         data[item]['minimum'],
                                                                                         data[item]['maximum'],
                                                                                         '%.3f' % data[item]['mean'],
                                                                                         data[item]['stdev'],
                                                                                         data[item]['mean_sql'],
                                                                                         data[item]['mean_sqltime'])
    return output


def generate_fields_from(data):
    output = list()

    header = ("view","method","status","count","minimum","maximum","mean",
              "stdev","queries","querytime")
    output.append(header)

    for item in sorted(data):
        row = [data[item]['view'],
               data[item]['method'],
               data[item]['status'],
               data[item]['count'],
               data[item]['minimum'],
               data[item]['maximum'],
               '%.3f' % data[item]['mean'],
               data[item]['stdev'],
               data[item]['mean_sql'],
               data[item]['mean_sqltime']]
        output.append([str(value) for value in row])

    widths = [max([len(r[i]) for r in output]) for i in range(len(header))]

    align = (["<"] * 3) + ([">"] * 7)
    template = " ".join(["{%d:%s%d}" % (i, align[i], w) for i, w in enumerate(widths)])

    footer = "\n(%d entries)" % len(data)
    return "\n".join([template.format(*row) for row in output]) + footer


def analyze_log_file(logfile, pattern, reverse_paths=True, progress=True):
    "Given a log file and regex group and extract the performance data"
    if progress:
        lines = count_lines_in(logfile)
        pbar = ProgressBar(widgets=[Percentage(), Bar()], maxval=lines+1).start()
    
    counter = 0
    data = AnalyzeAggregator()
    errors = []
    
    compiled_pattern = compile(pattern)
    ignored_patterns = [compile(p) for p in IGNORE_PATHS]

    for line in fileinput.input([logfile]):
        counter = counter + 1

        matches = compiled_pattern.findall(line)
        if not matches:
            errors.append({
                'line_number': counter,
                'line_content': line.strip(),
                })
            continue

        parsed = matches[0]
        date = parsed[0]
        method = parsed[1]
        path = parsed[2]
        status = parsed[3]
        time = parsed[4]
        sql = parsed[5]
        sqltime = parsed[6]

        ignore = any([p.match(path) for p in ignored_patterns])

        if not ignore:
            try:
                view = view_name_from(path) if reverse_paths else path
                data.add(view, status, method, float(time), int(sql), float(sqltime))
            except Resolver404:
                if reverse_paths:
                    data.add('__resolver404__', status, method, float(time), int(sql), float(sqltime))

        if progress:
            pbar.update(counter)
    
    if progress:
        pbar.finish()
    
    return data, errors


class AnalyzeAggregator(UserDict.IterableUserDict):
    def add(self, view, status, method, time, sql, sqltime):
        key = "%s-%s-%s" % (view, status, method)
        try:
            self[key]['count'] = self[key]['count'] + 1
            self[key]['times'].append(time)
            self[key]['sql'].append(sql)
            self[key]['sqltime'].append(sqltime)
        except KeyError:
            self[key] = {
                'count': 1,
                'status': status,
                'view': view,
                'method': method,
                'times': [time],
                'sql': [sql],
                'sqltime': [sqltime],
            }
