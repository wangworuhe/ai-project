from backend.extensions import db


class GrammarBook(db.Model):
    """A versioned source book imported into the grammar reader."""

    __tablename__ = "grammar_books"
    __table_args__ = (
        db.UniqueConstraint("slug", "edition", name="uq_grammar_book_slug_edition"),
    )

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    edition = db.Column(db.String(80), nullable=False)
    author = db.Column(db.String(160), nullable=True)
    source_filename = db.Column(db.String(500), nullable=False)
    source_sha256 = db.Column(db.String(64), nullable=False, index=True)
    total_pages = db.Column(db.Integer, nullable=False)
    imported_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    units = db.relationship(
        "GrammarUnit", back_populates="book", cascade="all, delete-orphan"
    )
    media = db.relationship(
        "GrammarMedia", back_populates="book", cascade="all, delete-orphan"
    )
    answer_key_entries = db.relationship(
        "GrammarAnswerKeyEntry", back_populates="book", cascade="all, delete-orphan"
    )


class GrammarUnit(db.Model):
    """One numbered unit and its source-page references."""

    __tablename__ = "grammar_units"
    __table_args__ = (
        db.UniqueConstraint("book_id", "unit_number", name="uq_grammar_unit_book_number"),
    )

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(
        db.Integer, db.ForeignKey("grammar_books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    grammar_point = db.Column(db.String(160), nullable=True)
    body_source_page = db.Column(db.Integer, nullable=False)
    exercise_source_page = db.Column(db.Integer, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(24), nullable=False, default="importing", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    book = db.relationship("GrammarBook", back_populates="units")
    content_blocks = db.relationship(
        "GrammarContentBlock", back_populates="unit", cascade="all, delete-orphan"
    )
    exercises = db.relationship(
        "GrammarExercise", back_populates="unit", cascade="all, delete-orphan"
    )
    media = db.relationship("GrammarMedia", back_populates="unit")


class GrammarContentBlock(db.Model):
    """An ordered semantic block from a unit's explanation or exercise page."""

    __tablename__ = "grammar_content_blocks"
    __table_args__ = (
        db.UniqueConstraint(
            "unit_id", "section", "sort_order", name="uq_grammar_content_block_order"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(
        db.Integer, db.ForeignKey("grammar_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section = db.Column(db.String(24), nullable=False)
    block_type = db.Column(db.String(32), nullable=False)
    content_json = db.Column(db.JSON, nullable=False)
    source_page = db.Column(db.Integer, nullable=False)
    source_bbox = db.Column(db.JSON, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    unit = db.relationship("GrammarUnit", back_populates="content_blocks")


class GrammarMedia(db.Model):
    """An image or other book asset stored directly in the database."""

    __tablename__ = "grammar_media"
    __table_args__ = (
        db.UniqueConstraint("book_id", "sha256", name="uq_grammar_media_book_sha256"),
    )

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(
        db.Integer, db.ForeignKey("grammar_books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_id = db.Column(
        db.Integer, db.ForeignKey("grammar_units.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mime_type = db.Column(db.String(100), nullable=False)
    content_blob = db.Column(db.LargeBinary, nullable=False)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    sha256 = db.Column(db.String(64), nullable=False)
    alt_text = db.Column(db.Text, nullable=True)
    source_page = db.Column(db.Integer, nullable=False)
    source_bbox = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    book = db.relationship("GrammarBook", back_populates="media")
    unit = db.relationship("GrammarUnit", back_populates="media")


class GrammarExercise(db.Model):
    """A numbered exercise group such as 1.1 or 1.2."""

    __tablename__ = "grammar_exercises"
    __table_args__ = (
        db.UniqueConstraint(
            "unit_id", "exercise_number", name="uq_grammar_exercise_unit_number"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(
        db.Integer, db.ForeignKey("grammar_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_number = db.Column(db.String(24), nullable=False)
    instruction = db.Column(db.Text, nullable=False)
    exercise_type = db.Column(db.String(32), nullable=False)
    word_bank_json = db.Column(db.JSON, nullable=True)
    source_page = db.Column(db.Integer, nullable=False)
    source_bbox = db.Column(db.JSON, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    unit = db.relationship("GrammarUnit", back_populates="exercises")
    questions = db.relationship(
        "GrammarQuestion", back_populates="exercise", cascade="all, delete-orphan"
    )


class GrammarQuestion(db.Model):
    """One numbered item within an exercise group."""

    __tablename__ = "grammar_questions"
    __table_args__ = (
        db.UniqueConstraint(
            "exercise_id", "question_number", name="uq_grammar_question_exercise_number"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    exercise_id = db.Column(
        db.Integer,
        db.ForeignKey("grammar_exercises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_number = db.Column(db.String(24), nullable=False)
    question_type = db.Column(db.String(32), nullable=False)
    content_json = db.Column(db.JSON, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False)
    is_example = db.Column(db.Boolean, nullable=False, default=False)
    source_page = db.Column(db.Integer, nullable=False)
    source_bbox = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    exercise = db.relationship("GrammarExercise", back_populates="questions")
    answer_slots = db.relationship(
        "GrammarAnswerSlot", back_populates="question", cascade="all, delete-orphan"
    )
    solution = db.relationship(
        "GrammarSolution", back_populates="question", cascade="all, delete-orphan", uselist=False
    )


class GrammarAnswerSlot(db.Model):
    """One answerable position in a question; a question may contain several."""

    __tablename__ = "grammar_answer_slots"
    __table_args__ = (
        db.UniqueConstraint("question_id", "slot_key", name="uq_grammar_answer_slot_key"),
        db.UniqueConstraint("question_id", "slot_order", name="uq_grammar_answer_slot_order"),
    )

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(
        db.Integer,
        db.ForeignKey("grammar_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slot_key = db.Column(db.String(64), nullable=False)
    slot_order = db.Column(db.Integer, nullable=False)
    answer_type = db.Column(db.String(32), nullable=False, default="text")
    normalization_rule = db.Column(db.String(48), nullable=False, default="english-text")
    points = db.Column(db.Numeric(6, 2), nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    question = db.relationship("GrammarQuestion", back_populates="answer_slots")


class GrammarAnswerKeyEntry(db.Model):
    """One source-faithful item from the book's complete Key to Exercises."""

    __tablename__ = "grammar_answer_key_entries"
    __table_args__ = (
        db.UniqueConstraint(
            "book_id",
            "unit_number",
            "exercise_number",
            "item_number",
            name="uq_grammar_answer_key_business_key",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(
        db.Integer,
        db.ForeignKey("grammar_books.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_number = db.Column(db.Integer, nullable=False, index=True)
    exercise_number = db.Column(db.String(24), nullable=False, index=True)
    item_number = db.Column(db.String(24), nullable=False)
    answer_text = db.Column(db.Text, nullable=False)
    answer_json = db.Column(db.JSON, nullable=False)
    is_example_answer = db.Column(db.Boolean, nullable=False, default=False)
    source_page = db.Column(db.Integer, nullable=False, index=True)
    source_printed_page = db.Column(db.Integer, nullable=False)
    source_label = db.Column(db.String(100), nullable=False)
    source_blocks_json = db.Column(db.JSON, nullable=False)
    parser_version = db.Column(db.String(32), nullable=False)
    content_sha256 = db.Column(db.String(64), nullable=False)
    verification_status = db.Column(
        db.String(24), nullable=False, default="parsed", index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    book = db.relationship("GrammarBook", back_populates="answer_key_entries")
    solution = db.relationship(
        "GrammarSolution", back_populates="answer_key_entry", uselist=False
    )


class GrammarSolution(db.Model):
    """The source-faithful answer-key entry for one question."""

    __tablename__ = "grammar_solutions"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(
        db.Integer,
        db.ForeignKey("grammar_questions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    answer_key_entry_id = db.Column(
        db.Integer,
        db.ForeignKey("grammar_answer_key_entries.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    answer_kind = db.Column(db.String(32), nullable=False)
    display_answer = db.Column(db.Text, nullable=False)
    grading_mode = db.Column(db.String(24), nullable=False, default="normalized")
    is_example = db.Column(db.Boolean, nullable=False, default=False)
    note = db.Column(db.Text, nullable=True)
    source_page = db.Column(db.Integer, nullable=False)
    source_label = db.Column(db.String(80), nullable=False)
    verification_status = db.Column(db.String(24), nullable=False, default="pending", index=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    question = db.relationship("GrammarQuestion", back_populates="solution")
    answer_key_entry = db.relationship(
        "GrammarAnswerKeyEntry", back_populates="solution"
    )
    variants = db.relationship(
        "GrammarAnswerVariant", back_populates="solution", cascade="all, delete-orphan"
    )


class GrammarAnswerVariant(db.Model):
    """One complete, valid combination of values for a solution's answer slots."""

    __tablename__ = "grammar_answer_variants"
    __table_args__ = (
        db.UniqueConstraint(
            "solution_id", "variant_order", name="uq_grammar_answer_variant_order"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    solution_id = db.Column(
        db.Integer,
        db.ForeignKey("grammar_solutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_order = db.Column(db.Integer, nullable=False)
    values_json = db.Column(db.JSON, nullable=False)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    source_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    solution = db.relationship("GrammarSolution", back_populates="variants")


class GrammarAttempt(db.Model):
    __tablename__ = "grammar_attempts"

    id = db.Column(db.Integer, primary_key=True)
    unit_number = db.Column(db.Integer, nullable=False, index=True)
    question_id = db.Column(db.String(64), nullable=False, index=True)
    prompt = db.Column(db.Text, nullable=False)
    user_answer = db.Column(db.Text, nullable=False)
    accepted_answers = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())


class GrammarMistake(db.Model):
    __tablename__ = "grammar_mistakes"

    id = db.Column(db.Integer, primary_key=True)
    unit_number = db.Column(db.Integer, nullable=False, index=True)
    question_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    grammar_point = db.Column(db.String(120), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    user_answer = db.Column(db.Text, nullable=False)
    accepted_answers = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, nullable=False)
    wrong_count = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(24), nullable=False, default="reviewing")
    last_seen_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
