from dj_anonymizer.register_models import register_skip

from thetatauCMT.trainings.models import EdCourse, Training, VectorGroup

register_skip([EdCourse, Training, VectorGroup])
