from behave import then, when


@when('I visit the path "{path}"')
def step_visit_path(context, path):
    context.response = context.test.client.get(path)


@then("the response status should be {status_code:d}")
def step_response_status(context, status_code):
    actual_status = context.response.status_code
    assert actual_status == status_code, (
        f"Expected status {status_code}, got {actual_status}"
    )


@then('the response should contain "{text}"')
def step_response_contains_text(context, text):
    content = context.response.content.decode("utf-8")
    assert text in content, f'Response did not contain "{text}"'
