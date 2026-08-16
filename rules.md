# 🌳 BUDH
### Knowledge Belongs to Everyone.

## important

 This document is the single source of truth for the BUDH project.

Any developer or AI contributing to this project must read and follow this document before making changes.

If a change conflicts with these rules, the rules take priority.

---

# Project Vision

BUDH is a modern educational search platform whose mission is to make trusted educational knowledge easily accessible to every student.

BUDH is **not** a blog.

BUDH is **not** another government portal.

BUDH is a search-first educational platform that connects students with reliable books, scholarships, exams, question papers, resources and educational opportunities.

Every design and engineering decision should support this mission.

---

# Philosophy

Knowledge belongs to everyone.

The website should always feel:

• Simple
• Fast
• Trustworthy
• Professional
• Modern
• Accessible

If a feature makes the website more confusing, it should not be added.

---

# Core Principles

## 1. Simplicity

If Google can remove something, so can we.

The homepage should remain minimal.

The search bar is the primary focus.

---

## 2. Trust

Every educational resource should come from trusted sources whenever possible.

Government websites should always be preferred over third-party websites.

Never intentionally include misleading information.

---

## 3. Scalability

Never write code that will need to be rewritten later.

Always build features so they can scale from:

10 resources

to

100,000+ resources.

---

## 4. Consistency

Every page should feel like part of the same product.

Use the same:

colors

spacing

buttons

cards

animations

typography

navigation

footer

---

# Tech Stack

Frontend

HTML5

CSS3

Vanilla JavaScript

Backend (Future)

Node.js

Database (Future)

JSON

Later:

SQLite

or

PostgreSQL

---

# Folder Structure

/
│
├── index.html
│
├── css/
│     style.css
│
├── js/
│     app.js
│     loader.js
│
├── assets/
│     logo.svg
│     favicon.png
│
├── pages/
│     about.html
│     sources.html
│     contribute.html
│
├── data/
│     books.json
│     scholarships.json
│     pyqs.json
│     olympiads.json
│     updates.json
│     resources.json
│
└── BUDH.md

Never change this structure unless absolutely necessary.

---

# Design System

Style

Minimal

Professional

Google-inspired

Modern

Flat

Clean

Soft

No visual clutter.

---

# Colors

Primary Blue

#163B69

Accent Blue

#2563EB

Background

#F8FAFC

Text

#1E293B

Secondary Text

#64748B

Cards

White

---

# Typography

Primary

Inter

Fallback

Segoe UI

Arial

sans-serif

---

# UI Components

Always reuse components.

Cards

Buttons

Badges

Search bar

Footer

Navigation

should all remain visually consistent.

---

# Homepage Rules

Homepage should contain only:

Logo

Title

Tagline

Search Bar

Quick Links

Footer

No unnecessary text.

No advertisements.

No hero images.

No distractions.

---

# Search Engine

Search should load databases once.

Search should support:

Title

Description

Subject

Board

Tags

Future support:

Synonyms

Typos

Fuzzy search

Ranking

Filters

---

# JSON Structure

Every JSON object should follow the same schema.

Example

{
"id":1,
"title":"",
"description":"",
"category":"",
"board":"",
"subject":"",
"class":"",
"language":"",
"price":"",
"verified":true,
"official":true,
"tags":[],
"url":""
}

Never create inconsistent JSON structures.

---

# Code Rules

Keep functions small.

Avoid duplicate code.

Never hardcode repeated values.

Comment important logic.

Prefer readability over clever code.

Use meaningful variable names.

Never sacrifice maintainability for short code.

---

# Performance

Load JSON only once.

Avoid unnecessary DOM updates.

Use DocumentFragment when rendering many cards.

Lazy-load future heavy assets.

Optimize images.

Prefer SVG icons.

---

# Accessibility

Semantic HTML.

Keyboard navigation.

Visible focus states.

Good color contrast.

Meaningful alt text.

Responsive on:

Desktop

Tablet

Mobile

---

# Animation Rules

Animations should be subtle.

Fast.

Smooth.

Purposeful.

Never distracting.

Avoid excessive motion.

---

# Future Features

Search Suggestions

Category Filters

Bookmarks

Dark Mode

Student Accounts

AI Search Assistant

Regional Languages

Offline Support

Teacher Dashboard

Admin Panel

API

---

# Never Do

Never rewrite working architecture.

Never rename project folders without reason.

Never introduce frameworks.

Never use Bootstrap.

Never use Tailwind.

Never use jQuery.

Never break existing functionality.

Never duplicate components.

Never hardcode future data.

---

# AI Instructions

If an AI modifies this project:

Preserve existing architecture.

Modify only what is necessary.

Never rewrite entire files unnecessarily.

Prefer extending existing code.

Always explain major architectural decisions.

Maintain consistency with this document.

---

# Current Status

✅ Homepage

✅ About Page

✅ Sources Page

✅ Contribute Page

✅ Logo

✅ Favicon

✅ Search Bar

✅ Search Engine

✅ books.json

🚧 Scholarships Database

🚧 Resources Database

🚧 Olympiads Database

🚧 PYQs Database

🚧 Updates Database

---

# Long-Term Vision

BUDH should become India's most trusted free educational search platform.

Every student should be able to discover verified educational resources within seconds.

Knowledge belongs to everyone.