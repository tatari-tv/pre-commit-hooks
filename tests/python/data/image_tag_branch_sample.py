class DatabricksJobOperator:
    def __init__(self, branch=str | None, image_tag=str | None, task_id=str):
        self.branch = branch
        self.image_tag = image_tag
        self.task_id = task_id


class Operator:
    def __init__(self, branch=str | None, image_tag=str | None, task_id=str):
        self.branch = branch
        self.image_tag = image_tag
        self.task_id = task_id


# This is a valid usage, should not be flagged
valid_operator = DatabricksJobOperator(task_id='valid_task', job_id='12345')

# This should be flagged (DatabricksJobOperator with image_tag)
job_operator_with_image_tag = DatabricksJobOperator(task_id='task_with_image_tag', job_id='12345', image_tag='some_tag')

# This should be flagged (DatabricksJobOperator with branch)
job_operator_with_branch = DatabricksJobOperator(task_id='task_with_branch', job_id='12345', branch='some_branch')

# Another valid usage, should not be flagged
another_valid_operator = DatabricksJobOperator(task_id='another_valid_task', job_id='54321')

# Another invalid usage, should be flagged twice
another_job_operator_with_image_tag = DatabricksJobOperator(
    task_id='another_task_with_image_tag', job_id='54321', image_tag='another_tag', branch='another_branch'
)

# valid usage, should not be flagged
fake_operator_with_image_tag = Operator(task_id='another_task_with_image_tag', job_id='54321', image_tag='another_tag')
