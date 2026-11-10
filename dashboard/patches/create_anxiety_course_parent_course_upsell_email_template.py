"""
Seeds the "Anxiety Course - Parent Course Upsell" Email Template -
Ashley's copy for the follow-up email sent 5 days after someone buys
the Primary Anxiety Toolkit (£29) LMS course, pitching The Resilient
Kid Parent Course (£199). Sent by the Email Sequence engine (see
create_anxiety_course_upsell_sequence.py), not a one-off send, so this
only ever seeds the template - same self-healing re-run approach as
create_franchise_brochure_link_email_template.py (only writes content
into a blank subject/body, so re-running this after Ashley has edited
the template in Desk never clobbers her edits).

Authored as full custom HTML (headings, bold emphasis, bullet lists,
two CTA buttons) rather than plain text, since Ashley's copy needs all
of that and the Email Sequence engine's plain-text path only wraps
each line in its own <p> - already wrapped in the site's own branded
shell (logo header + wordmark footer) so it reads as every other
outgoing email does.
"""

import frappe

from dashboard.api.shared.email_templates import ANXIETY_COURSE_UPSELL_TEMPLATE, wrap_branded_email_html

TEMPLATE_NAME = ANXIETY_COURSE_UPSELL_TEMPLATE

SUBJECT = "You've started helping your child with anxiety. Now let's build their resilience."

PARENT_COURSE_URL = "https://theresilienthub.co.uk/trh-courses/a-parents-course-to-raising-a-resilient-kid"

_TEAL = "#00A19E"


def _button_html(label, url):
    return f"""
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px auto;">
      <tr>
        <td style="border-radius:6px; background-color:{_TEAL};">
          <a href="{url}" target="_blank" rel="noopener"
             style="display:inline-block; padding:14px 28px; font-size:15px; font-weight:bold;
                    color:#ffffff; text-decoration:none; border-radius:6px;">
            {label}
          </a>
        </td>
      </tr>
    </table>
    """


def _gains_section():
    gains = [
        ("Understanding your child's brain and behaviour",
         "Discover what's happening beneath the surface, why children react the way they do and how to respond with greater understanding."),
        ("Building emotional regulation",
         "Help your child recognise, understand and manage big feelings, while learning how your own responses can support them."),
        ("Growing confidence and self-belief",
         "Support your child to develop a stronger inner voice, try new things, make mistakes and believe in their ability to cope."),
        ("Navigating friendships and relationships",
         "Help your child develop healthy friendships, understand boundaries, manage disagreements and build a sense of belonging."),
        ("Encouraging independence and problem-solving",
         "Learn when to step in, when to step back and how to help your child develop their own solutions."),
        ("Creating stronger connections",
         "Build a relationship where your child feels heard, understood, supported and safe enough to come to you when things get difficult."),
    ]
    return "".join(
        f'<p style="margin:0 0 4px;"><strong>{title}</strong></p>'
        f'<p style="margin:0 0 18px;">{body}</p>'
        for title, body in gains
    )


def _body_html():
    return f"""
    <h1 style="color:{_TEAL}; font-size:22px; line-height:1.3; margin:0 0 18px;">
      You&rsquo;ve Started Helping Your Child With Anxiety. Now Let&rsquo;s Build Their Resilience.
    </h1>

    <p>Because helping your child isn&rsquo;t just about managing their worries today. It&rsquo;s about giving them the tools to navigate life tomorrow.</p>

    <p><strong>You&rsquo;ve already taken an important step.</strong></p>

    <p>By investing in our £29 Anxiety Course, you&rsquo;ve started to understand what&rsquo;s happening when your child feels worried, overwhelmed or anxious.</p>

    <p>Perhaps you&rsquo;ve discovered why reassurance doesn&rsquo;t always work, why anxiety can show up as anger or avoidance, or why your child can hold everything together at school and fall apart at home.</p>

    <p><strong>But here&rsquo;s something I want you to know.</strong></p>

    <p>You don&rsquo;t need to wait until your child is struggling to help them become resilient.</p>

    <p>And you don&rsquo;t have to have all the answers.</p>

    <h2 style="color:{_TEAL}; font-size:19px; margin:28px 0 6px;">Introducing The Resilient Kid Parent Course</h2>
    <p style="font-style:italic; margin:0 0 14px;">From managing anxiety to raising a confident, emotionally resilient child.</p>
    <p><strong>£199 &ndash; Your investment in understanding and supporting your child.</strong></p>

    <p>Parenting can be wonderful, exhausting, confusing and overwhelming. Sometimes all in the same afternoon!</p>

    <p>One minute your child is happy and confident. The next, they&rsquo;re refusing to go to school, falling out with friends, having a meltdown or telling you they can&rsquo;t do something.</p>

    <p>And you&rsquo;re left wondering:</p>
    <ul style="margin:0 0 16px; padding-left:20px;">
      <li>Am I saying the right thing?</li>
      <li>Should I step in or let them work it out?</li>
      <li>Why does my child behave differently at home?</li>
      <li>How do I help them without making their anxiety worse?</li>
      <li>How do I build their confidence without putting pressure on them?</li>
      <li>Am I doing enough?</li>
    </ul>

    <p>Here&rsquo;s the good news. You don&rsquo;t have to be a perfect parent. You just need the right understanding and some practical tools.</p>

    <p>That&rsquo;s exactly why I created The Resilient Kid Parent Course.</p>

    <h2 style="color:{_TEAL}; font-size:19px; margin:28px 0 10px;">Anxiety Is Just One Piece of the Puzzle</h2>

    <p>Your child is growing up in a world full of challenges, expectations and pressures.</p>
    <p>There will be friendships that go wrong, mistakes, disappointments, difficult emotions, changes and moments when they doubt themselves.</p>
    <p>We can&rsquo;t remove every challenge from our children&rsquo;s lives.</p>
    <p><strong>But we can help them develop the skills to navigate them.</strong></p>
    <p>And it starts with us.</p>
    <p>Not by fixing everything for them.</p>
    <p>Not by protecting them from every uncomfortable feeling.</p>
    <p>But by becoming the safe, supportive adult who helps them understand themselves, develop confidence and discover what they&rsquo;re capable of.</p>

    <h2 style="color:{_TEAL}; font-size:19px; margin:28px 0 10px;">What Will You Gain From the Parent Course?</h2>
    <p>Through practical, accessible learning, we&rsquo;ll help you explore:</p>
    {_gains_section()}

    <h2 style="color:{_TEAL}; font-size:19px; margin:28px 0 10px;">You Don&rsquo;t Need to Get Parenting Right 100% of the Time</h2>
    <p>One of the most important things I teach parents is that children don&rsquo;t need perfect parenting.</p>
    <p>They need connection.<br>They need consistency.<br>They need someone who believes in them, particularly when they&rsquo;re struggling to believe in themselves.</p>
    <p>And sometimes the smallest changes in how we respond can create the biggest ripples.</p>
    <p><strong>Connection before correction. Understanding before judgement. Support without taking over.</strong></p>
    <p>That&rsquo;s how we start building resilience.</p>

    <h2 style="color:{_TEAL}; font-size:19px; margin:28px 0 10px;">Why Learn With The Resilient Kid?</h2>
    <p>I&rsquo;m Ashley Costello, founder of The Resilient Kid, psychotherapist, author and someone who has spent nearly 30 years supporting children, young people and families.</p>
    <p>I&rsquo;ve seen firsthand how powerful it can be when parents begin to understand what&rsquo;s really going on for their child.</p>
    <p>Sometimes it takes just one person to change a child&rsquo;s life.</p>
    <p>And very often, that person is already there.</p>
    <p><strong>It&rsquo;s you.</strong></p>
    <p>My mission is to help one million children build resilience, and I believe supporting the adults around them is one of the most powerful ways to make that happen.</p>
    <p>This isn&rsquo;t about giving you another list of things you&rsquo;re doing wrong.</p>
    <p>It&rsquo;s about helping you recognise what you&rsquo;re already doing well and giving you practical, realistic ways to build on it.</p>

    <h2 style="color:{_TEAL}; font-size:19px; margin:28px 0 10px;">You&rsquo;ve Taken the First Step. Are You Ready for the Next?</h2>
    <p>&#10003; <strong>Anxiety Course &ndash; £29</strong><br>Understand your child&rsquo;s anxiety and learn practical ways to support them through worries and overwhelm.</p>
    <p>&#10003; <strong>The Resilient Kid Parent Course &ndash; £199</strong><br>Go beyond anxiety and develop a broader toolkit to support your child&rsquo;s emotional wellbeing, confidence, friendships, independence and resilience.</p>
    <p><strong>Your next step: £199</strong></p>

    {_button_html("YES! I WANT TO HELP MY CHILD BUILD RESILIENCE", PARENT_COURSE_URL)}

    <h2 style="color:{_TEAL}; font-size:19px; margin:28px 0 10px;">A Final Thought&hellip;</h2>
    <p>Imagine your child being able to say:</p>
    <p style="margin:0 0 4px;">&ldquo;I can try, even if I&rsquo;m worried.&rdquo;</p>
    <p style="margin:0 0 4px;">&ldquo;I know what to do when things feel difficult.&rdquo;</p>
    <p style="margin:0 0 4px;">&ldquo;It&rsquo;s OK to make mistakes.&rdquo;</p>
    <p style="margin:0 0 4px;">&ldquo;I can ask for help.&rdquo;</p>
    <p style="margin:0 0 18px;">&ldquo;I believe in myself.&rdquo;</p>

    <p>That&rsquo;s what we&rsquo;re working towards.</p>
    <p>Not a childhood without challenges.</p>
    <p>A child who knows they have the tools, support and confidence to face them.</p>
    <p>And it starts with the adults who care about them.</p>
    <p><strong>Let&rsquo;s build their resilience together.</strong></p>

    {_button_html("JOIN THE RESILIENT KID PARENT COURSE &ndash; £199", PARENT_COURSE_URL)}
    """


def _is_blank(value):
    return not (value or "").strip()


def execute():
    if not frappe.db.exists("DocType", "Email Template"):
        return

    # Reuses email_templates.py's own _body_fieldname rather than a
    # simplified local copy - this content is genuine HTML (headings,
    # bold, bullet lists, two buttons), so it matters that it lands in
    # "response_html" on a site using that use_html/Quill split, not
    # "response" (the rich-text editor), which is why use_html has to be
    # set BEFORE asking _body_fieldname which field to use - that's
    # exactly what it reads to decide.
    from dashboard.api.shared.email_templates import _body_fieldname

    body = wrap_branded_email_html(_body_html())

    try:
        is_new = not frappe.db.exists("Email Template", TEMPLATE_NAME)
        doc = frappe.new_doc("Email Template") if is_new else frappe.get_doc("Email Template", TEMPLATE_NAME)

        if doc.meta.has_field("use_html"):
            doc.use_html = 1

        body_fieldname = _body_fieldname(doc)
        if not body_fieldname:
            frappe.log_error(
                "Email Template has none of the expected body fields. "
                f"Actual fields: {[f.fieldname for f in doc.meta.fields]}",
                "Create Anxiety Course Upsell Email Template - No Body Field Found",
            )
            return

        if not is_new and (not _is_blank(doc.get("subject")) or not _is_blank(doc.get(body_fieldname))):
            return

        if doc.meta.has_field("subject"):
            doc.subject = SUBJECT

        doc.set(body_fieldname, body)

        if is_new:
            doc.name = TEMPLATE_NAME
            doc.insert(ignore_permissions=True)
        else:
            doc.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Create Anxiety Course Upsell Email Template Failed: {TEMPLATE_NAME}")

    frappe.db.commit()
