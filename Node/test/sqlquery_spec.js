const expect = require('chai').expect;
const SqlQuery = require('../');

describe('sqlQuery', () => {
    describe('new', () => {
        let sqlQuery = new SqlQuery('mock-api-key', 'mock-crn', 'https://');

        it('returns object', () => {
            expect(sqlQuery).to.be.a('object');
        });

        it('has function runSql()', () => {
            expect(sqlQuery).to.have.property('runSql').to.be.a('function');
        });
    });
});