CREATE EXTENSION IF NOT EXISTS vector;
-- Separate database for the automated test-suite.
SELECT 'CREATE DATABASE finsight_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'finsight_test')\gexec
