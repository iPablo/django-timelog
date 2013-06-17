from django.conf import settings
from django.views.generic.base import TemplateView

from .lib import analyze_log_file, add_stats_to, PATTERN

class TimelogView(TemplateView):
    template_name = 'timelog/home.html'

    def get_context_data(self, **kwargs):
        context = super(TimelogView, self).get_context_data(**kwargs)

        raw_data = analyze_log_file(settings.TIMELOG_LOG, PATTERN, reverse_paths=True, progress=False)
        data = add_stats_to(raw_data).values()
        context['data'] = sorted(data, key=lambda record: record['mean'], reverse=True)
        return context