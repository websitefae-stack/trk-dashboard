"""
Seeds the real content for the "Franchise Brochure" Single doctype -
previously just the "Brochure content coming soon." placeholder (see
franchise_brochure.py/the resilient_domains www page's own fallback),
since nothing had ever filled this field in. Ashley confirmed the
content to use is the existing /trh-franchise page's own body (pasted
directly from that page, which isn't in any repo this session has
access to - it's built straight on the live site) - this is a literal
copy of it, with only its own {{ web_block(...) }} nav/footer calls
stripped out (those are Jinja calls baked into the live page's own
template; a raw string pulled from this field and rendered via
Jinja's `| safe` would show them as literal text, not re-evaluate
them - /franchise-brochure's own index.html already supplies its own
nav/footer chrome).

Its styling (trh-services-page, trh-hero, trh-service-grid, etc) lives
in a CSS file that also isn't in any repo - see trh-franchise-
brochure.css, a copy of what Ashley pasted, linked by both
/franchise-brochure/index.html and the PDF download wrapper.

Runs once on the next `bench migrate` - re-running later (if this
patch somehow fired twice) would simply overwrite with the same
content, so no idempotency guard needed beyond Frappe's own patch
tracking (every patch here only ever runs once per site).
"""

import frappe

DOCTYPE_NAME = "Franchise Brochure"

CONTENT = """<div class="trh-page trh-services-page">

  <!-- =====================================================
       HERO
  ====================================================== -->
  <section class="trh-hero">
    <div class="trh-container">
      <div class="trh-hero-grid">

        <div>
          <div class="trh-eyebrow">The Resilient Franchise&trade;</div>

          <h1>Own your own business. Make a bigger impact.</h1>

          <p class="trh-hero-text">
            Welcome to The Resilient Kid franchise opportunity. This is your
            chance to be your own boss, join an established brand and help
            future-proof the next generation.
          </p>

          <div class="trh-buttons">
            <a href="#investment" class="trh-btn trh-btn-primary">
              View Investment
            </a>

            <a href="#what-is-included" class="trh-btn trh-btn-secondary">
              See What&rsquo;s Included
            </a>
          </div>
        </div>

        <div class="trh-hero-panel">
          <div class="trh-hero-panel-inner">
            <span>Empowering Coaches</span>
            <span>Empowering Children aged 4&ndash;12</span>
            <span>Training, support and community</span>
            <span>Build a business that makes a difference</span>
          </div>
        </div>

      </div>
    </div>
  </section>


  <!-- =====================================================
       INTRO - WHITE
  ====================================================== -->
  <section class="trh-section">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">Become a Resilient Kid Coach</div>

        <h2>Be a business owner, but never feel alone.</h2>

        <p>
          Led by Ashley Costello, a seasoned psychotherapist with 30 years of
          experience, our framework is tried, tested and proven to make a
          lasting impact on children&rsquo;s lives.
        </p>
      </div>

      <div class="trh-service-grid">

        <div class="trh-service-card trh-service-therapy">
          <h3>Be your own boss</h3>
          <p>
            All coaches are self-employed, but you will be part of our team.
            We will all be working towards the same goals and supporting each
            other fearlessly.
          </p>
        </div>

        <div class="trh-service-card trh-service-workshops">
          <h3>Have a role that&rsquo;s FUN</h3>
          <p>
            Even though Resilient Kid Coaches will be helping kids through
            some very tough times, every coach will be valued and their
            well-being honoured.
          </p>
        </div>

        <div class="trh-service-card trh-service-cpd">
          <h3>Have a BIGGER impact</h3>
          <p>
            Resilient Kid Coaches are taught how to make a greater impact in
            the lives of their clients and are equipped with the tools to do so.
          </p>
        </div>

      </div>

      <div class="trh-section-header trh-section-follow">
        <p>
          There are children out there in your community right now, waiting
          for someone to really see and hear them.
        </p>

        <h2>Be that someone.</h2>
      </div>

    </div>
  </section>


  <!-- =====================================================
       DEMAND - LIGHT BLUE
  ====================================================== -->
  <section class="trh-section trh-section-soft">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">The demand</div>
        <h2>How long will it take to build a client base?</h2>
        <p>Let&rsquo;s first take a look at the demand.</p>
      </div>

      <div class="trh-service-grid">

        <div class="trh-service-card trh-service-therapy">
          <h3>1 in 5</h3>
          <p>
            1 in 5 children are currently struggling with their mental health,
            that&rsquo;s an average of 6 kids in every UK classroom.
          </p>
        </div>

        <div class="trh-service-card trh-service-cpd">
          <h3>52% increase</h3>
          <p>
            Children&rsquo;s mental health services have had a 52% increase in
            referrals in 2023/24.
          </p>
        </div>

        <div class="trh-service-card trh-service-books">
          <h3>392 days</h3>
          <p>
            64% of referrals did not receive treatment, and those that did
            had to wait an average of 392 days.
          </p>
        </div>

      </div>

      <div class="trh-two-col trh-section-follow">

        <div>
          <h2>We know they deserve better.</h2>
        </div>

        <div>
          <p>
            We know that mental health impacts on all aspects of their life,
            including their educational attainment, relationships and
            physical well-being.
          </p>

          <p>
            Families are looking for help but there isn&rsquo;t enough out there.
            Parents just can&rsquo;t afford to wait for CAMHS to support them, as
            they are dealing with 500 referrals a day for anxiety alone.
          </p>

          <p><strong>There is a clear demand.</strong></p>

          <p>
            As a Resilient Kid Coach you could be providing immediate,
            effective help and free up the waiting list for others.
          </p>
        </div>

      </div>
    </div>
  </section>


  <!-- =====================================================
       BUILDING YOUR BUSINESS - WHITE
  ====================================================== -->
  <section class="trh-section">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">Building your business</div>
        <h2>So how long will it take to get enough clients?</h2>

        <p>
          The truth is it does depend. Deciding to become a Resilient Kid
          Coach is also a decision to become a business owner, and part of
          the role involves building your network and advertising your services.
        </p>
      </div>

      <div class="trh-two-col">

        <div>
          <div class="trh-hero-panel">
            <div class="trh-hero-panel-inner">
              <span>10 clients = &pound;3,250 per month</span>
              <span>15 clients = &pound;4,875 per month</span>
            </div>
          </div>
        </div>

        <div>
          <p>
            Don&rsquo;t worry though, not only is the demand there but The Resilient
            Kid HQ is here to help you tap into it.
          </p>

          <p>
            We provide you with all the business support you need, including
            marketing and audience building, and the whole reason this model
            has been franchised is because it&rsquo;s constantly over-subscribed.
          </p>

          <p>
            We know that parents are crying out for help. We know there aren&rsquo;t
            enough services and resources to support them. We know that many
            are willing and able to pay &mdash; and they do.
          </p>

          <p>
            To replace your current income, you don&rsquo;t even need hundreds of clients.
          </p>

          <p>
            While we can&rsquo;t give specific timelines, we can promise to give you
            the tools and support you need to earn enough money doing fewer hours.
          </p>
        </div>

      </div>
    </div>
  </section>


  <!-- =====================================================
       TEAM - LIGHT BLUE
  ====================================================== -->
  <section class="trh-section trh-section-soft">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">The team</div>
        <h2>Meet the people behind The Resilient Kid</h2>
      </div>

      <div class="trh-team-grid">

        <article class="trh-team-card">

          <div class="trh-team-image-wrap">
            <img
              src="/files/Ashley.png"
              alt="Ashley Costello"
              class="trh-team-image"
            >
          </div>

          <div class="trh-team-content">
            <h3>Ashley Costello</h3>

            <p class="trh-team-role">
              Founder of The Resilient Kid
            </p>

            <p>
              Ashley is the founder of The Resilient Kid and a psychotherapist
              with 30 years of experience helping children, teens and families
              build resilience and emotional wellbeing.
            </p>
          </div>

        </article>


        <article class="trh-team-card">

          <div class="trh-team-image-wrap">
            <img
              src="/files/Chantelle.png"
              alt="Chantelle Venter"
              class="trh-team-image"
            >
          </div>

          <div class="trh-team-content">
            <h3>Chantelle Venter</h3>

            <p class="trh-team-role">
              Business Manager
            </p>

            <p>
              Chantelle supports the business and franchisees in the backend and keeps us all on track.
            </p>
          </div>

        </article>

      </div>

    </div>
  </section>


  <!-- =====================================================
       FRAMEWORK - WHITE
  ====================================================== -->
  <section class="trh-section">
    <div class="trh-container">

      <div class="trh-two-col">

        <div>
          <div class="trh-eyebrow">The framework</div>
          <h2>Why is the Resilient Kid Method unique?</h2>
        </div>

        <div>
          <p>
            The Resilient Kid is different from others. Our framework holds
            sessions with the children and parents.
          </p>

          <p>
            Our method is designed to equip children with the tools they need
            to navigate life&rsquo;s challenges with confidence and resilience.
            Not only that, we educate parents and teachers to support the child too.
          </p>

          <p>
            Through a blend of evidence-based techniques, interactive activities
            and personalised coaching, we help children develop crucial life
            skills such as emotional regulation, problem-solving and positive
            coping strategies.
          </p>
        </div>

      </div>

    </div>
  </section>


  <!-- =====================================================
       COMPREHENSIVE TRAINING - LIGHT BLUE
       WHITE CARDS
  ====================================================== -->
  <section class="trh-section trh-section-soft trh-comprehensive-section">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">Comprehensive training</div>

        <h2>Everything you need to deliver the programme confidently.</h2>

        <p>
          As a franchisee, you will receive comprehensive training in our
          framework, led by Ashley Costello herself.
        </p>
      </div>

      <div class="trh-service-grid">

        <div class="trh-service-card trh-service-cpd">
          <h3>Two-day initial training</h3>
          <p>
            Benefit from Ashley&rsquo;s wealth of experience and expertise as you
            become proficient in delivering an impactful The Resilient Kid programme.
          </p>
        </div>

        <div class="trh-service-card trh-service-therapy">
          <h3>Safeguarding</h3>
          <p>
            You will have safeguarding training which you need by law to be
            working with children and young people. The cost of this training
            is covered in your fee.
          </p>
        </div>

        <div class="trh-service-card trh-service-workshops">
          <h3>Ongoing supervision</h3>
          <p>
            Additional training throughout the year, monthly 1:1 supervision
            calls with Ashley and group calls with your fellow Resilient Kid Coaches.
          </p>
        </div>

      </div>

      <div class="trh-section-header trh-business-heading">
        <div class="trh-eyebrow">Building your business</div>
        <h2>Business training includes</h2>

        <p>
          You are not just learning how to deliver the programme. We help you
          develop the skills you need to build and grow your own local business.
        </p>
      </div>

      <div class="trh-business-training-grid">

        <div class="trh-training-pill">Marketing</div>
        <div class="trh-training-pill">Social Media</div>
        <div class="trh-training-pill">Public Speaking</div>
        <div class="trh-training-pill">Copywriting</div>

        <div class="trh-training-pill">LinkedIn</div>
        <div class="trh-training-pill">Business Coaching</div>
        <div class="trh-training-pill">Accountancy</div>
        <div class="trh-training-pill">PR</div>

        <div class="trh-training-pill">Networking</div>
        <div class="trh-training-pill">Canva &amp; Graphics</div>
        <div class="trh-training-pill">Frappe Systems</div>
        <div class="trh-training-pill">Client Onboarding</div>

      </div>

    </div>
  </section>


  <!-- =====================================================
       EXPERT VILLAGE - LIGHT BLUE
       SMALL WHITE CARDS
  ====================================================== -->
  <section class="trh-section trh-section-soft trh-expert-section">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">Expert Village</div>

        <h2>It takes a village to build a successful business too.</h2>

        <p>
          Raising a child truly takes a village, and as a Resilient Kid Coach,
          you&rsquo;re going to be a vital part of that community.
        </p>

        <p>
          That&rsquo;s why we&rsquo;ve assembled an outstanding team of experts to support
          you every step of the way.
        </p>
      </div>

      <div class="trh-expert-grid">

        <div class="trh-expert-card">
          <h3>Lisa Barry</h3>
          <p>Mission Led Content training.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Catherine Sandland</h3>
          <p>Helping people share it, teach it and sell it.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Lynda Pepper</h3>
          <p>Social Media Marketing Manager.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Ali Ford</h3>
          <p>Soul-aligned brand photography.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Sally Tyson</h3>
          <p>Graphic design and branding.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Harriet Wignall-Parry</h3>
          <p>Affordable accountancy support.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Paula Cohen</h3>
          <p>Business coaching for small business owners.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Helen Tudor</h3>
          <p>LinkedIn training.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Sarah Vogel</h3>
          <p>Building better conversations.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Washington Ali</h3>
          <p>Young people&rsquo;s confidence.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Michelle &amp; Christian Ewen</h3>
          <p>PR and media support.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Georgia Osborne</h3>
          <p>ADHD coaching.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Susie Sprigg</h3>
          <p>Networking at its best.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Lisa Danielles</h3>
          <p>Teaching how to use TikTok.</p>
        </div>

        <div class="trh-expert-card">
          <h3>Chantelle Venter</h3>
          <p>Frappe and business systems training.</p>
        </div>

      </div>

    </div>
  </section>


  <!-- =====================================================
       FAMILY TESTIMONIALS - WHITE
       BLUE TESTIMONIAL CARDS
  ====================================================== -->
  <section class="trh-section trh-family-section">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">What families say</div>
        <h2>What Families Have To Say About Working With Ashley</h2>
      </div>

      <div class="trh-family-testimonials">

        <article class="trh-testimonial-card trh-testimonial-main">

          <p>
            Ashley has helped both us and our daughter in far more ways than
            it would be possible to write about in one review! From the initial,
            apprehensive enquiry phone call I made, right through to the present
            day. She was on hand throughout a lengthy, and often extremely
            frustrating, diagnostic process. She listened, supported (and
            challenged when required), educated and advocated. At times it felt
            like every professional in the world was against us, yet Ashley
            walked by all our sides.... nothing ever seemed too much. The
            flexibility (and frequency) of her sessions ensures that they are
            always needs-led and her vast knowledge and tool kit means that
            adaptability is never an issue. I would not hesitate to recommend
            contacting Ashley if you feel you and your family could benefit
            from her help and expertise. A very grateful parent.
          </p>

          <h3>Val and Daughter, aged 16</h3>

        </article>

        <div class="trh-testimonial-stack">

          <article class="trh-testimonial-card trh-testimonial-green">

            <p>
              Our daughter is always at her happiest on days when she has seen
              Ashley. I have seen her grow in terms of her ability to manage a
              range of emotions and feelings as well as being more confident
              in her own self-worth.
            </p>

            <h3>Amelia &amp; Mia, aged 11</h3>

          </article>

          <article class="trh-testimonial-card trh-testimonial-orange">

            <p>
              Ashley is absolutely fantastic. The work she completed with our
              daughter was brilliant. We went from treading on eggshells around
              her, to enjoying her again. Thank you.
            </p>

            <h3>Lily &amp; Isla, aged 7</h3>

          </article>

        </div>

      </div>

    </div>
  </section>


  <!-- =====================================================
       FROM OUR COACHES - LIGHT BLUE
       WHITE CARDS
  ====================================================== -->
  <section class="trh-section trh-section-soft">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">From our coaches</div>
        <h2>What It&rsquo;s Like To Work Along Side Ashley</h2>
      </div>

      <div class="trh-service-grid">

        <div class="trh-service-card trh-service-therapy">
          <p>
            I hadn&rsquo;t realised just how much value there was in the training and
            resources I received from joining The Resilient Kid. When I started
            attending networking events with other small businesses, I quickly
            saw that I already had so many of the tools and insights others
            were searching for. Ashley&rsquo;s years of knowledge and expertise shine
            through, and she shares it so generously.
          </p>

          <p>
            Although this is my own franchise, I feel truly blessed to be part
            of a supportive team that I can reach out to&mdash;knowing they&rsquo;re on the
            same path as me. I&rsquo;m genuinely excited to see where my business
            journey takes me next.
          </p>

          <h3>Emily Parker</h3>
          <p>The Resilient Kid Coach in Chester and the surrounding area</p>
        </div>

        <div class="trh-service-card trh-service-cpd">
          <p>
            Joining the Resilient Kid Franchise has been an absolute
            game-changer. The training is a one-stop shop for everything you
            need to get your business moving in the right direction. What stood
            out most for me was the sense of belonging. I may be on my own
            business journey, but I&rsquo;m now part of a family that genuinely has
            my back.
          </p>

          <h3>Fiona Kennedy</h3>
          <p>The Resilient Kid Coach in Bramhall, Cheadle Hulme, Poynton</p>
        </div>

        <div class="trh-service-card trh-service-workshops">
          <p>
            I absolutely loved the training and would rate it 10 out of 10.
            The material was really easy to understand and I felt supported
            every step of the way, even when I didn&rsquo;t realise I needed support.
            Ashley is always there to answer questions and offer guidance, and
            that ongoing connection has been invaluable.
          </p>

          <h3>Sarah-Jane Falconer</h3>
          <p>The Resilient Kid Coach in Homes Chapel, Sandbach, Middlewich</p>
        </div>

      </div>

    </div>
  </section>


  <!-- =====================================================
       MAGIC OF FRANCHISING - WHITE
       BLUE CARDS
  ====================================================== -->
  <section class="trh-section trh-franchising-section">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">The magic of franchising</div>

        <h2>
          Want to be your own boss but afraid of starting your own business?
        </h2>
      </div>

      <div class="trh-service-grid">

        <div class="trh-service-card trh-blue-card trh-service-books">
          <h3>Join an established brand</h3>
          <p>
            Save time and resources building your business from the beginning.
            Consumers are often more willing to trust businesses with
            established brands.
          </p>
        </div>

        <div class="trh-service-card trh-blue-card trh-service-cpd">
          <h3>Join a proven business model</h3>
          <p>
            Instead of taking a risk, franchised businesses have proven the
            model works and the demand is there.
          </p>
        </div>

        <div class="trh-service-card trh-blue-card trh-service-shop">
          <h3>Get training and support</h3>
          <p>
            Get the skills and guidance you need to run a successful business.
            Never be alone.
          </p>
        </div>

      </div>

      <div class="trh-section-header trh-section-follow">
        <h2>Have a higher chance of success</h2>

        <p>
          Compared to independent startups, franchises have a higher success rate.
        </p>

        <p>
          A franchise is a safe and exciting way to become a business owner.
        </p>

        <p>
          According to the Natwest Franchise survey over 90% of franchisees
          are successful compared to only 47% of independent businesses.
        </p>
      </div>

    </div>
  </section>


  <!-- =====================================================
       WHAT IS INCLUDED - LIGHT BLUE
       WHITE TRAINING + SUPPORT CARDS
  ====================================================== -->
  <section class="trh-section trh-section-soft trh-included-section" id="what-is-included">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">What is included?</div>

        <h2>Training, support and resources to get you started.</h2>

        <p>
          From learning the framework to building your local presence and
          running the systems behind your business, we support both sides of
          becoming a Resilient Kid franchisee.
        </p>
      </div>

      <div class="trh-included-heading">
        <span>01</span>

        <div>
          <div class="trh-eyebrow">Learn &amp; build</div>
          <h2>Training</h2>
        </div>
      </div>

      <div class="trh-included-grid">

        <div class="trh-included-card">The Resilient Kid Framework</div>
        <div class="trh-included-card">Accessing your emails</div>
        <div class="trh-included-card">Client management software</div>

        <div class="trh-included-card">Accounting</div>
        <div class="trh-included-card">Graphics and Branding</div>
        <div class="trh-included-card">Social media &mdash; Facebook &amp; Instagram</div>

        <div class="trh-included-card">Branding shots &mdash; photography</div>
        <div class="trh-included-card">LinkedIn</div>
        <div class="trh-included-card">Mission Led Content</div>

        <div class="trh-included-card">Business coaching</div>
        <div class="trh-included-card">Talking about your business</div>
        <div class="trh-included-card">Building a network strategy</div>

        <div class="trh-included-card">The stories we should be telling</div>
        <div class="trh-included-card">Tracking your mileage</div>
        <div class="trh-included-card">Tracking your CPD</div>

        <div class="trh-included-card">Fierce Principles</div>
        <div class="trh-included-card">Networking &mdash; C.O.N.N.E.C.T Method</div>
        <div class="trh-included-card">PR training</div>

        <div class="trh-included-card">Confidence</div>
        <div class="trh-included-card">Managing ADHD</div>
        <div class="trh-included-card">Onboarding &amp; Offboarding Clients</div>

      </div>


      <div class="trh-included-heading trh-included-support-heading">
        <span>02</span>

        <div>
          <div class="trh-eyebrow">You are not doing it alone</div>
          <h2>Support</h2>
        </div>
      </div>

      <div class="trh-support-grid">

        <div class="trh-support-card">Ongoing email support</div>
        <div class="trh-support-card">Monthly one-to-one</div>
        <div class="trh-support-card">Monthly group supervision</div>

        <div class="trh-support-card">Coaches Community</div>
        <div class="trh-support-card">Personalised Website page</div>
        <div class="trh-support-card">Operations manual</div>

        <div class="trh-support-card">Community Platform</div>
        <div class="trh-support-card">Training Hub</div>
        <div class="trh-support-card">Resource Hub</div>

      </div>

    </div>
  </section>


  <!-- =====================================================
       EQUIPMENT - WHITE
       BLUE SMALL CARDS
  ====================================================== -->
  <section class="trh-section trh-equipment-section">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">Equipment</div>
        <h2>Your starter kit</h2>
      </div>

      <div class="trh-service-grid">

        <div class="trh-service-card trh-blue-card trh-service-therapy">
          <h3>Branded clothing</h3>
          <p>Polo shirt or T-shirt</p>
          <p>Soft shell jacket or Fleece or Body Warmer</p>
        </div>

        <div class="trh-service-card trh-blue-card trh-service-cpd">
          <h3>Books &amp; journals</h3>
          <p>10 x A parents guide to raising a resilient kid</p>
          <p>10 x Resilient kid journal</p>
          <p>10 x Book 1 - Framework</p>
        </div>

        <div class="trh-service-card trh-blue-card trh-service-workshops">
          <h3>Resources</h3>
          <p>1 x Tote bag</p>
          <p>10 x Branded pens</p>
          <p>10 x Kids pencils</p>
          <p>1 x Brave jar</p>
        </div>

        <div class="trh-service-card trh-blue-card trh-service-books">
          <h3>Workbooks</h3>
          <p>5 x Worries workbook</p>
          <p>5 x Anger workbook</p>
          <p>5 x Confidence workbook</p>
          <p>5 x Emotions workbook</p>
        </div>

        <div class="trh-service-card trh-blue-card trh-service-shop">
          <h3>Toolboxes</h3>
          <p>10 x Toolbox and stickers</p>
        </div>

      </div>

    </div>
  </section>


  <!-- =====================================================
       WHY CHOOSE - LIGHT BLUE
  ====================================================== -->
  <section class="trh-section trh-section-soft">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">Why choose us?</div>
        <h2>Why Choose The Resilient Kid Franchise?</h2>
      </div>

      <div class="trh-reason-grid">

        <div class="trh-reason-card">
          <span>01</span>
          <h3>Proven Success</h3>
          <p>
            Our methodology has been meticulously developed and refined over
            years of practical application, yielding consistently positive
            results for children and families.
          </p>
        </div>

        <div class="trh-reason-card">
          <span>02</span>
          <h3>Comprehensive Training</h3>
          <p>
            Receive comprehensive training in our framework led by Ashley,
            alongside Marketing, Social Media, Public Speaking and other
            specialist business training.
          </p>
        </div>

        <div class="trh-reason-card">
          <span>03</span>
          <h3>Monthly supervision by Ashley</h3>
          <p>
            Individual supervision alongside a community support group,
            supporting you in both your practice and your business.
          </p>
        </div>

        <div class="trh-reason-card">
          <span>04</span>
          <h3>Business in a Box</h3>
          <p>
            Marketing materials, equipment, operational guidance and ongoing
            support to help you hit the ground running.
          </p>
        </div>

        <div class="trh-reason-card">
          <span>05</span>
          <h3>Flexibility and Fulfilment</h3>
          <p>
            Set your own schedule while doing deeply rewarding work with
            children and families, both face-to-face and where appropriate online.
          </p>
        </div>

        <div class="trh-reason-card">
          <span>06</span>
          <h3>Community</h3>
          <p>
            Connect with a growing community of Resilient Kid Coaches through
            Zoom, daily community support, in-person training and events.
          </p>
        </div>

      </div>

      <div class="trh-section-header trh-section-follow">
        <p>
          We are future-proofing the next generation. No one expects you to do
          that alone. Let&rsquo;s do it together. Collaborate, connect, create.
        </p>

        <h2>
          Make a difference in your own life and community whilst building a
          fulfilling career.
        </h2>
      </div>

    </div>
  </section>


  <!-- =====================================================
       INVESTMENT - WHITE
  ====================================================== -->
  <section class="trh-section" id="investment">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">Investment Fee</div>
        <h2>Your investment in becoming a Resilient Kid Coach</h2>
      </div>

      <div class="trh-pathway-grid">

        <div class="trh-pathway-card trh-card-kid">
          <h3>&pound;5,999</h3>
          <p><strong>One-off payment</strong></p>
        </div>

        <div class="trh-pathway-card trh-card-school">
          <h3>&pound;1,500</h3>
          <p><strong>4 monthly payments</strong></p>
        </div>

      </div>

      <div class="trh-section-header trh-section-follow">

        <p>
          The investment fee of a Resilient Kid franchise is a limited-time
          opportunity designed to attract passionate partners who are eager
          to grow alongside us.
        </p>

        <p>
          This special rate won&rsquo;t last forever, so now is the perfect time to
          join our mission and secure your place in the Resilient Kid family.
        </p>

        <p>
          As one of our early franchisees, you&rsquo;ll benefit from being part of
          a company that&rsquo;s committed to supporting your success and expanding
          our impact together.
        </p>

      </div>

    </div>
  </section>


  <!-- =====================================================
       FINANCIALS - LIGHT BLUE
  ====================================================== -->
  <section class="trh-section trh-section-soft">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">Financials</div>
        <h2>The important bit!</h2>
      </div>

      <div class="trh-two-col">

        <div>
          <div class="trh-hero-panel">
            <div class="trh-hero-panel-inner">
              <span>&pound;5,999 or 4 &times; &pound;1,500</span>
              <span>Minimum &pound;100 or 10% royalty fees</span>
              <span>2% marketing fee</span>
              <span>First 2 months&rsquo; fees waived</span>
              <span>2-week fee holiday each year</span>
            </div>
          </div>
        </div>

        <div>
          <p>
            To buy into the Resilient Kid Franchise, it is &pound;5,999 or 4 monthly
            payments of &pound;1,500.
          </p>

          <p>
            Each month, there is a minimum payment of &pound;100 or 10% royalty fees
            plus a Marketing fee of 2% (which goes directly to market the brand
            nationally and locally), whichever is higher.
          </p>

          <p>
            As we want to support you on your journey to becoming a successful
            Resilient Kid Coach the first 2 months' Fees are waived. Only in
            month 3 will you start to pay the fees.
          </p>

          <p>
            To support your well-being we have also included a 2-week holiday
            a year, where you can take a holiday from fees.
          </p>
        </div>

      </div>

    </div>
  </section>


  <!-- =====================================================
       WE ARE SEEKING - WHITE
  ====================================================== -->
  <section class="trh-section">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">We&rsquo;re Seeking</div>
        <h2>Could this be you?</h2>

        <p>
          Individuals with a background in coaching, counselling, or education.
        </p>

        <p>
          Most importantly though we want people who have a desire to make a
          meaningful impact and future-proof the next generation.
        </p>

        <p>
          Whether you're an experienced educator, therapist, or childcare
          professional, The Resilient Kid franchise offers a unique opportunity
          to leverage your skills and expertise for the greater good.
        </p>

        <p>
          What&rsquo;s more, you can take control of your own future and create a
          more joyous life. Work fewer hours for more money and finally feel valued?
        </p>

        <p>
          Together, we can build a more resilient world, one child at a time.
        </p>
      </div>

    </div>
  </section>


  <!-- =====================================================
       YOUR JOURNEY - LIGHT BLUE
       WHITE CARDS + PURPLE SIDE LINES
       SECONDARY NOTES REMOVED
  ====================================================== -->
  <section class="trh-section trh-section-soft trh-journey-section">
    <div class="trh-container">

      <div class="trh-section-header">
        <div class="trh-eyebrow">Your Journey</div>

        <h2>Your Journey as a Resilient Kid Franchisee</h2>

        <p>
          From your first conversation to certification, we guide you through
          every stage of getting ready to launch your Resilient Kid business.
        </p>
      </div>

      <div class="trh-journey-grid">

        <div class="trh-journey-step">
          <span>01</span>
          <p>Initial Call with Our Recruitment Consultant</p>
        </div>

        <div class="trh-journey-step">
          <span>02</span>
          <p>Call with Ashley &mdash; Founder of Resilient Kid</p>
        </div>

        <div class="trh-journey-step">
          <span>03</span>
          <p>Sign an NDA &mdash; Non-Disclosure Agreement</p>
        </div>

        <div class="trh-journey-step">
          <span>04</span>
          <p>Discovery Day</p>
        </div>

        <div class="trh-journey-step">
          <span>05</span>
          <p>Intent to Proceed Document</p>
        </div>

        <div class="trh-journey-step">
          <span>06</span>
          <p>Franchisee Intake Form + DBS/Insurance Submitted</p>
        </div>

        <div class="trh-journey-step">
          <span>07</span>
          <p>Franchise Agreement Signed &amp; Invoice Paid</p>
        </div>

        <div class="trh-journey-step">
          <span>08</span>
          <p>Email Account Created</p>
        </div>

        <div class="trh-journey-step">
          <span>09</span>
          <p>&ldquo;Your Logins&rdquo; Hub Set Up</p>
        </div>

        <div class="trh-journey-step">
          <span>10</span>
          <p>Frappe Dashboard Access</p>
        </div>

        <div class="trh-journey-step">
          <span>11</span>
          <p>Training Day &mdash; Resilient Kid Values, Framework &amp; Brand Photoshoot</p>
        </div>

        <div class="trh-journey-step">
          <span>12</span>
          <p>Access to Your Emails &mdash; Training with Chantelle</p>
        </div>

        <div class="trh-journey-step">
          <span>13</span>
          <p>Course Access &mdash; A Parents Course to Raising a Resilient Kid</p>
        </div>

        <div class="trh-journey-step">
          <span>14</span>
          <p>Social Media Account Set Up &amp; Branded</p>
        </div>

        <div class="trh-journey-step">
          <span>15</span>
          <p>Email Signature Set Up</p>
        </div>

        <div class="trh-journey-step">
          <span>16</span>
          <p>Print Materials Ordered</p>
        </div>

        <div class="trh-journey-step">
          <span>17</span>
          <p>Policies &amp; Procedures Review</p>
        </div>

        <div class="trh-journey-step">
          <span>18</span>
          <p>Graphics &amp; Canva Training</p>
        </div>

        <div class="trh-journey-step">
          <span>19</span>
          <p>Social Media Training</p>
        </div>

        <div class="trh-journey-step">
          <span>20</span>
          <p>LinkedIn Training</p>
        </div>

        <div class="trh-journey-step">
          <span>21</span>
          <p>Mission-Led Content Training</p>
        </div>

        <div class="trh-journey-step">
          <span>22</span>
          <p>Public Speaking Training</p>
        </div>

        <div class="trh-journey-step">
          <span>23</span>
          <p>Networking Strategy Training</p>
        </div>

        <div class="trh-journey-step">
          <span>24</span>
          <p>PR Training</p>
        </div>

        <div class="trh-journey-step">
          <span>25</span>
          <p>Frappe Training &amp; Sandbox Practice</p>
        </div>

        <div class="trh-journey-step">
          <span>26</span>
          <p>Onboarding &amp; Offboarding Clients Training</p>
        </div>

        <div class="trh-journey-step">
          <span>27</span>
          <p>Live Frappe Follow-Up Session</p>
        </div>

        <div class="trh-journey-step">
          <span>28</span>
          <p>Accounts Training</p>
        </div>

        <div class="trh-journey-step">
          <span>29</span>
          <p>Business Coaching</p>
        </div>

        <div class="trh-journey-step">
          <span>30</span>
          <p>Final Checks</p>
        </div>

        <div class="trh-journey-step trh-journey-final">
          <span>31</span>
          <p>Certification</p>
        </div>

      </div>

    </div>
  </section>


  <!-- =====================================================
       FINAL CTA
  ====================================================== -->
  <section class="trh-cta">
    <div class="trh-container">

      <div class="trh-eyebrow trh-eyebrow-white">
        Become a Resilient Kid Coach Franchise Owner
      </div>

      <h2>Ready to explore becoming a Resilient Kid Coach?</h2>

      <p>
        Take the next step and find out more about the investment and what is
        included in becoming part of The Resilient Kid franchise.
      </p>

      <div class="trh-buttons trh-buttons-centred">
        <a href="#investment" class="trh-btn trh-btn-secondary">
          View Investment
        </a>
      </div>

    </div>
  </section>

</div>"""


def execute():
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    frappe.db.set_value(DOCTYPE_NAME, DOCTYPE_NAME, "content", CONTENT)
    frappe.db.commit()
