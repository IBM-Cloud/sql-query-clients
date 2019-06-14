const expect = require('chai').expect;
const SqlQuery = require('../');

describe('sqlQuery', () => {
    describe('new', () => {
        it('returns object', () => {
            let sqlQuery = new SqlQuery('mock-api-key', 'mock-crn', 'https://');
            expect(sqlQuery).to.have.property('runSql');
        });
    });
});