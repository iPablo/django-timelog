from optparse import make_option

from django.core.management.base import BaseCommand
from django.conf import settings

from timelog.lib import add_stats_to, generate_table_from, generate_csv_from, generate_fields_from, analyze_log_file, PATTERN


class Command(BaseCommand):

    generate_output_functions = {
        'table':  generate_table_from,
        'csv':    generate_csv_from,
        'fields': generate_fields_from,
    }

    option_list = BaseCommand.option_list + (
        make_option('--file',
            dest='file',
            default=settings.TIMELOG_LOG,
            help='Specify file to use'),
        make_option('--output',
            dest='output',
            default='table',
            help='Specify output format - valid choices are {0}'.format(generate_output_functions.keys())),
        make_option('--noreverse',
            dest='reverse',
            action='store_false',
            default=True,
            help='Show paths instead of views'),
        make_option('--showprogress',
            dest='progress',
            action='store_true',
            default=False,
            help='Show progress bar when analyzing the log file'),
        make_option('--showerrors',
            dest='showerrors',
            action='store_true',
            default=False,
            help='Show errors found in the log file'),
    )

    def handle(self, *args, **options):

        if options.get('output') not in self.generate_output_functions:
            print "Invalid output format, valid choices are {0}".format(self.generate_output_functions.keys())
            exit(2)

        LOGFILE = options.get('file')

        try:
            raw_data, errors = analyze_log_file(LOGFILE, PATTERN, reverse_paths=options.get('reverse'), progress=options.get('progress'))
        except IOError:
            print "File not found"
            exit(2)

        if options.get('showerrors'):
            if errors:
                print "Error reading the following lines:"
                for error in errors:
                    print "line %d: %s" % (error['line_number'], error['line_content'])
            else:
                print "No errors reading the log file"

        data = add_stats_to(raw_data)
        generate_output_fn = self.generate_output_functions[options.get('output')]
        print generate_output_fn(data)