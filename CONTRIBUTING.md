# Contributing to FSV Mainz 05 Interactive Database App

Thank you for your interest in contributing to this project! This guide will help you get started.

## 🎯 How to Contribute

We welcome contributions in the following areas:

- 🐛 **Bug Fixes**: Fix issues in the application
- ✨ **New Features**: Add new functionality
- 📝 **Documentation**: Improve or add documentation
- 🧪 **Tests**: Add or improve test coverage
- 🎨 **UI/UX**: Enhance the user interface
- ⚡ **Performance**: Optimize performance
- 🗄️ **Data**: Improve data parser or data quality

## 📋 Before You Start

1. **Check existing issues**: Look at [open issues](../../issues) to see if someone is already working on it
2. **Discuss major changes**: For significant features, open an issue first to discuss your approach
3. **Follow coding standards**: Review the code style guidelines below
4. **Read the documentation**: Familiarize yourself with the project structure

## 🚀 Getting Started

### 1. Fork & Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/pfem-uc1-05.git
cd pfem-uc1-05

# Add upstream remote
git remote add upstream https://github.com/ORIGINAL_OWNER/pfem-uc1-05.git
```

### 2. Install Dependencies

```bash
# Install all dependencies (root + workspaces)
npm install
```

### 3. Set Up Environment

Create `.env` file:

```bash
# Database (Required)
DB_URL=postgresql://user:password@host:port/fsv05?sslmode=require

# Google Gemini AI (Required)
GEMINI_API_KEY=your_gemini_api_key

# Optional: Langfuse Observability
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 4. Run Database Migrations

```bash
npm run db:migrate
```

### 5. Start Development

```bash
# Start both frontend and backend
npm run dev

# Or individually
npm run dev:api   # Backend only
npm run dev:web   # Frontend only
```

## 🔧 Development Workflow

### Creating a Branch

```bash
# Update your fork
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

**Branch Naming Convention:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions/changes
- `perf/` - Performance improvements

### Making Changes

1. **Write clean code**: Follow the style guidelines below
2. **Add tests**: For new features and bug fixes
3. **Update docs**: If you change APIs or add features
4. **Test thoroughly**: Run all tests before committing

### Running Tests

```bash
# Run all tests
npm run test

# Backend tests
cd apps/api
npm run test

# Unit tests only (no DB required)
npm run test:unit

# Integration tests (requires DB)
npm run test:integration

# E2E tests
npm run test:e2e

# Watch mode
npm run test:watch
```

### Linting & Formatting

```bash
# Run linter
npm run lint

# Fix lint issues
npm run lint:fix

# Format code (if available)
npm run format
```

### Building

```bash
# Build all apps
npm run build

# Build individual apps
cd apps/api && npm run build
cd frontend && npm run build
```

## 📝 Coding Standards

### TypeScript

#### General Guidelines

- Use TypeScript for all new code
- Prefer interfaces over types for object shapes
- Use explicit return types for functions
- Avoid `any` - use `unknown` if type is truly unknown
- Use strict null checks

#### Example

```typescript
// ✅ Good
interface User {
  id: string;
  name: string;
  email: string;
}

function getUser(id: string): Promise<User | null> {
  // Implementation
}

// ❌ Bad
function getUser(id: any): any {
  // Implementation
}
```

### React

#### Component Structure

```typescript
// ✅ Preferred structure
import React, { useState, useEffect } from 'react';
import { ComponentProps } from './types';

export const MyComponent: React.FC<ComponentProps> = ({ prop1, prop2 }) => {
  // 1. Hooks
  const [state, setState] = useState<string>('');

  // 2. Event handlers
  const handleClick = () => {
    setState('new value');
  };

  // 3. Effects
  useEffect(() => {
    // Side effect
  }, []);

  // 4. Render
  return (
    <div className="container">
      <button onClick={handleClick}>{prop1}</button>
    </div>
  );
};
```

#### Component Guidelines

- Use functional components with hooks
- Extract complex logic into custom hooks
- Keep components small and focused
- Use meaningful component and prop names
- Prefer composition over inheritance

### Backend (Fastify)

#### Route Structure

```typescript
// ✅ Good route handler
import { FastifyRequest, FastifyReply } from 'fastify';
import { z } from 'zod';

const requestSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
});

export async function createUser(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const data = requestSchema.parse(request.body);
    const user = await userService.create(data);
    return reply.status(201).send(user);
  } catch (error) {
    if (error instanceof z.ZodError) {
      return reply.status(400).send({ error: 'Validation failed', details: error.errors });
    }
    throw error;
  }
}
```

#### Backend Guidelines

- Use Zod for validation
- Return appropriate HTTP status codes
- Handle errors gracefully
- Use async/await (avoid callbacks)
- Validate all user input

### Database

#### Migrations

```sql
-- migrations/XXX_description.sql

BEGIN;

-- Use transactions
-- Make migrations reversible when possible
-- Add comments for complex changes

CREATE TABLE example (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for foreign keys
CREATE INDEX idx_example_name ON example(name);

COMMIT;
```

#### Query Guidelines

- Use parameterized queries (prevent SQL injection)
- Add indexes for frequently queried columns
- Use transactions for multi-step operations
- Test queries for performance
- Document complex queries

### Git Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `perf`: Performance improvements
- `chore`: Maintenance tasks

**Examples:**

```bash
# Good commits
git commit -m "feat(quiz): add difficulty selection"
git commit -m "fix(chat): resolve message ordering issue"
git commit -m "docs(api): update endpoint documentation"
git commit -m "test(quiz): add unit tests for score calculation"

# Bad commits
git commit -m "update stuff"
git commit -m "fix bug"
git commit -m "changes"
```

## 🧪 Testing Guidelines

### What to Test

- **Unit Tests**: Individual functions, utilities, components
- **Integration Tests**: API endpoints, database queries
- **E2E Tests**: Critical user flows (chat, quiz)

### Writing Tests

#### Backend Test Example (Vitest)

```typescript
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { createUser, getUser } from './userService';

describe('User Service', () => {
  beforeEach(async () => {
    // Setup
  });

  afterEach(async () => {
    // Cleanup
  });

  it('should create a user', async () => {
    const userData = { name: 'Test User', email: 'test@example.com' };
    const user = await createUser(userData);

    expect(user).toBeDefined();
    expect(user.name).toBe('Test User');
    expect(user.email).toBe('test@example.com');
  });

  it('should throw error for invalid email', async () => {
    const userData = { name: 'Test User', email: 'invalid-email' };

    await expect(createUser(userData)).rejects.toThrow('Invalid email');
  });
});
```

#### Frontend Test Example (Vitest + Testing Library)

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Button } from './Button';

describe('Button Component', () => {
  it('renders with correct text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('calls onClick handler when clicked', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click me</Button>);

    fireEvent.click(screen.getByText('Click me'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Click me</Button>);
    expect(screen.getByText('Click me')).toBeDisabled();
  });
});
```

## 📚 Documentation Guidelines

### Code Comments

- Document complex logic
- Explain "why", not "what"
- Use JSDoc for functions and classes
- Keep comments up-to-date

```typescript
// ❌ Bad comment (obvious)
// Increment counter by 1
counter++;

// ✅ Good comment (explains why)
// Increment counter to track retries before falling back to cache
counter++;
```

### JSDoc Example

```typescript
/**
 * Calculates the quiz score based on answer time
 *
 * @param answerTimeMs - Time taken to answer in milliseconds
 * @param maxTime - Maximum allowed time in milliseconds
 * @returns Score between 10 (slowest) and 100 (fastest)
 *
 * @example
 * calculateScore(5000, 30000) // Returns ~83 points
 */
function calculateScore(answerTimeMs: number, maxTime: number): number {
  // Implementation
}
```

### README Updates

When adding features:
1. Update the main README.md
2. Update relevant component READMEs (apps/api, frontend)
3. Add examples and usage instructions
4. Update the documentation index

## 🔍 Pull Request Process

### Before Submitting

- [ ] All tests pass (`npm run test`)
- [ ] Code follows style guidelines (`npm run lint`)
- [ ] Build succeeds (`npm run build`)
- [ ] Documentation is updated
- [ ] Commits follow convention
- [ ] Branch is up-to-date with main

### Submitting a PR

1. **Push your changes**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request** on GitHub

3. **Fill out PR template**
   - Describe the changes
   - Link related issues
   - Add screenshots for UI changes
   - List any breaking changes

4. **Request review** from maintainers

### PR Template

```markdown
## Description
Brief description of what this PR does

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Refactoring

## Changes Made
- Change 1
- Change 2
- Change 3

## Related Issues
Closes #123

## Testing
Describe how you tested these changes

## Screenshots (if applicable)
[Add screenshots here]

## Checklist
- [ ] Tests pass
- [ ] Linter passes
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. Maintainers review your code
2. Address any feedback
3. Once approved, maintainers will merge

## 🐛 Reporting Bugs

### Before Reporting

1. Check [existing issues](../../issues)
2. Verify it's reproducible
3. Collect relevant information

### Bug Report Template

```markdown
## Bug Description
A clear description of the bug

## Steps to Reproduce
1. Go to '...'
2. Click on '...'
3. See error

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: [e.g., macOS 13.0]
- Node.js: [e.g., 20.10.0]
- Browser: [e.g., Chrome 120]

## Additional Context
Screenshots, error logs, etc.
```

## 💡 Feature Requests

### Feature Request Template

```markdown
## Feature Description
Clear description of the feature

## Problem it Solves
What problem does this solve?

## Proposed Solution
How would this feature work?

## Alternatives Considered
What other solutions did you consider?

## Additional Context
Mockups, examples, etc.
```

## 📦 Project-Specific Guidelines

### Working with AI Prompts

Prompts are located in `/prompts/fallback/`:

1. **Langfuse (Preferred)**: Prompts managed in Langfuse cloud
2. **Local Fallback**: Files in `/prompts/fallback/*.txt`

When updating prompts:
- Test changes thoroughly with sample queries
- Document prompt versions
- Update both Langfuse and local fallbacks

### Database Changes

When modifying the schema:

1. Create migration file: `database/migrations/XXX_description.sql`
2. Test migration on test database
3. Update schema documentation: `docs/SCHEMA_DOCUMENTATION_2025.md`
4. Run migration: `npm run db:migrate`

### Parser Updates

When updating the data parser (`parsing/comprehensive_fsv_parser.py`):

1. Update parser code
2. Run on test season: `python parsing/comprehensive_fsv_parser.py`
3. Verify data quality
4. Update documentation: `docs/PARSER_IMPROVEMENTS.md`

## 🤝 Community Guidelines

- Be respectful and inclusive
- Provide constructive feedback
- Help others when possible
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md)

## 📞 Getting Help

- 💬 **Discussions**: [GitHub Discussions](../../discussions)
- 🐛 **Issues**: [GitHub Issues](../../issues)
- 📖 **Documentation**: [docs/](docs/)

## 🎉 Recognition

Contributors will be:
- Listed in the project README
- Mentioned in release notes
- Added to CONTRIBUTORS.md (if significant contributions)

---

Thank you for contributing to FSV Mainz 05 Interactive Database App! ⚽❤️
