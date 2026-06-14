"""In-memory / fixed test doubles for every domain port.

These are fully implemented (unlike ``infrastructure/``) because they are
trivial and central to demonstrating that ``application.use_cases`` are
unit-testable via constructor injection alone -- no mocking framework
required.
"""
