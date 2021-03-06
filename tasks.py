from celery import Celery
import mongoengine

from ded.Recipe import Recipe
from ded.DataProvider import DataProvider

celery = Celery('daily-ebook',
            broker="redis://redis:6379/0",
            backend="redis://redis:6379/0")
celery.conf.task_routes = ([
    ('ebook_generator.*', {'queue': 'eg'}),
    ('data_provider.*', {'queue': 'dp'})
],)

# mongoengine.connect('celery_beat_daily_epub') useless for now
"""confs = {
    "CELERY_MONGODB_SCHEDULER_DB": "celery_beat_daily_epub",
    "CELERY_MONGODB_SCHEDULER_COLLECTION" : "schedules", # we can't really change this, there is no current_app according to
    "CELERY_MONGODB_SCHEDULER_URL" : "mongodb://mongo:27017"
}
celery.conf.update(confs)"""

@celery.task(bind=True, name="data_provider.get_sources_metadata")
def get_sources_metadata(self):
    # FIXME: improve this to only load modules one time
    data_provider = DataProvider()
    metadatas = []
    for source_name, source in data_provider.modules.items():
        metadatas.append(source.metadata)
    return {'sources': metadatas}

# bind=True to have the self parameter
@celery.task(bind=True, name="data_provider.generate_book_from_dict_recipe")
def generate_book_from_dict_recipe(self, recipe_dict):
    self.update_state(state='PROGRESS', meta={'type': 'update', 'message': 'Starting...'})
    recipe = Recipe.from_dict(recipe_dict)
    self.update_state(state='PROGRESS', meta={'type': 'update', 'message': 'Fetching data'})
    recipe.build()
    self.update_state(state='PROGRESS', meta={'type': 'update', 'message': 'Rendering to HTML'})
    recipe.render()
    recipe_dict = recipe.to_dict()
    render_task = celery.send_task('ebook_generator.render_recipe_to_ebook', args=[recipe_dict], kwargs={})
    return {
        'type': 'new-task',
        'message': 'Deferred execution to task {0}'.format(render_task.id),
        'task-id': render_task.id,
        'preview-html': recipe_dict["html"]
    }


